import random
from telebot import TeleBot
from telebot.types import Message
from telebot import types
from database import create_database, insert_new_word, update_word, select_word, update_level
from process import str_in_list_dict, remove_double_word, list_in_str_dict
from config import TOKEN, CUR_USER_DICT, STEP_USER, DONE_USER_DICT
from time import sleep
from random import sample
import datetime
from scheduler import create_job, check_interval_word, cur_date_now

bot = TeleBot(TOKEN)


def key(buttons_text):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2, one_time_keyboard=True)
    markup.add(*buttons_text)
    return markup

@bot.message_handler(commands=['start'])
def start_handler(message: Message):
    bot.send_message(message.chat.id,
                     'Привет! Я бот для запоминания слов.\nНапиши /new чтобы добавить слово и перевод. \nНапиши /list чтобы посмотреть все слова.\n'
                     'Напиши /update чтобы обновить значение слова.')


@bot.message_handler(commands=['help'])
def help_handler(message: Message):
    bot.send_message(message.chat.id, '/new - добавить слово и перевод. \n/list - посмотреть все слова.\n'
                                      '/update - обновить значение слова.')


@bot.message_handler(commands=['new'])
def new_word_info_handler(message: Message):
    bot.send_message(message.chat.id,
                     'Напиши слово и перевод в формате: слово=перевод, можно в одно сообщение. Не используй цифры в слове')


@bot.message_handler(func=lambda message: '=' in message.text)
def new_word_handler(message: Message):
    cur_list_dict, report_int = str_in_list_dict(message.text)

    if not cur_list_dict:
        bot.send_message(message.chat.id, report_int)
        return

    list_dict, report_check = remove_double_word(message.chat.id, cur_list_dict)
    report = report_int + report_check  # Репорт наличие цифр и наличия слов в БД

    if report and list_dict == []:  # добавить проверку на цифры
        bot.send_message(message.chat.id, 'Слова уже есть в словаре')
        return

    if report:
        bot.send_message(message.chat.id, report)
        sleep(1)
        str_dict1 = list_in_str_dict(list_dict)
        bot.send_message(message.chat.id, str_dict1)
    markup = key(['Да', 'Нет'])
    bot.send_message(message.chat.id, 'Если всё верно, то нажмите Да', reply_markup=markup)
    bot.register_next_step_handler(message, double_check, list_dict)


def double_check(message, dict_user):
    if message.text == 'Да':
        date_dict = datetime.date.fromtimestamp(message.json['date'])

        report = ''
        for element in dict_user:  # list
            report += insert_new_word(message.chat.id, [element[0], element[1], date_dict])

        if not report:
            report = 'Сохранено'
        else:
            report = 'Ошибка во время добавления в БД'
        bot.send_message(message.chat.id, report)
    else:
        bot.send_message(message.chat.id, 'Введите слова ещё раз')
        bot.register_next_step_handler(message, new_word_handler)
    create_job(bot, message.chat.id)

@bot.message_handler(commands=['update'])
def handle_update_command(message):
    bot.reply_to(message, "Напиши слово и новый перевод в формате: слово=новый_перевод. Не используй цифры и знаки")
    user_id = message.from_user.id

    def get_update_word(msg):
        try:
            text = msg.text
            word, translation = map(str.strip, text.split('=', 1))

            if not word.isalnum():
                bot.send_message(message.chat.id, 'Слово не должно содержать букв')
                bot.register_next_step_handler(message, get_update_word)
                return

            update_word(user_id, word, translation)  # вызов функции обновления в БД
            bot.reply_to(msg, f"Перевод для слова '{word}' успешно обновлен на '{translation}'.")
        except ValueError:
            bot.reply_to(msg, "Ошибка в формате. Пожалуйста, используй формат: /update слово=перевод.")

    bot.register_next_step_handler(message, get_update_word)


@bot.message_handler(commands=['list'])
def list_handler(message: Message):
    dict_user_all = select_word(message.chat.id)

    if type(dict_user_all) == type('str'):
        bot.send_message(message.chat.id, dict_user_all)
        return

    list_user = list_in_str_dict(dict_user_all)
    bot.send_message(message.chat.id, list_user)


def saving_progress(user_id):
    dict_write = DONE_USER_DICT[user_id]

    for word_list in dict_write:
        word, level_word, date_now = word_list
        update_level(user_id, word, level_word, date_now)
    bot.send_message(user_id, 'Сохранил!')
    return


@bot.message_handler(commands=['play'])
def play_handler(message: Message):
    dict_user = select_word(message.chat.id)
    cur_dict_user = []

    if type(dict_user) == type('str'):
        bot.send_message(message.chat.id, dict_user)
        return

    for element in dict_user:
        if check_interval_word(element):
            cur_dict_user.append(element)

    count_word = min(10, len(dict_user))
    CUR_USER_DICT[message.chat.id] = sample(dict_user, count_word)
    bot.send_message(message.chat.id,
                     'Вывести список слов для повторения: /list_words.\nИли начать повторение /repeat.\n'
                     '/exit - выход')
    bot.register_next_step_handler(message, repeat_list)


def repeat_list(message: Message):
    DONE_USER_DICT[message.chat.id] = []
    if message.text == '/repeat':
        STEP_USER[message.chat.id] = len(CUR_USER_DICT[message.chat.id])
        repeat(message)
        return

    elif message.text == '/list_words': #добавить кнопку, скрывающую это сообщение
        list_words = CUR_USER_DICT[message.chat.id].copy()
        random.shuffle(list_words)

        text_words = list_in_str_dict(list_words)
        bot.send_message(message.chat.id, text_words)
        bot.register_next_step_handler(message, repeat_list)
        return

    elif message.text == '/exit':
        bot.send_message(message.chat.id, 'Выход из режима повторения...')
        return

    else:
        bot.send_message(message.chat.id,
                         '/list_words - список повторяемых слов.\n/repeat - начать повторение\nВыход - /exit.')
        bot.register_next_step_handler(message, repeat_list)


def repeat(message: Message):
    list_words = CUR_USER_DICT[message.chat.id]
    len_words = len(list_words)

    if len_words == 0:
        bot.send_message(message.chat.id, 'Молодец, повторил все слова. Обновляю таблицу...')
        saving_progress(message.chat.id)
        return


    bot.send_message(message.chat.id, f'Напишите перевод слова {list_words[0][1]}')
    bot.register_next_step_handler(message, replay, list_words[0])


def replay(message: Message, list_word):
    word, trans, level_word, date_word = list_word
    answer_us = message.text
    if answer_us == '/exit':
        bot.send_message(message.chat.id, 'Жду нашей встречи вновь.\n Обновляю таблицу...')
        saving_progress(message.chat.id)
        return

    if not answer_us.isalnum():
        bot.send_message(message.chat.id, 'Введите ответ без цифр')
        bot.register_next_step_handler(message, list_word)
        return

    if answer_us == word:
        bot.send_message(message.chat.id,
                         'Верно.')
        level_word += 1 # Ещё нужно спрашивать чела, правильно или нет

        date_now = cur_date_now()
        list_word_now = [word, level_word, date_now]

        cur_word_repeat = DONE_USER_DICT[message.chat.id]
        cur_word_repeat.append(list_word_now)

    else:
        bot.send_message(message.chat.id, f'Правильное написание: {word}')

    list_words = CUR_USER_DICT[message.chat.id]

    list_words.pop(0)
    CUR_USER_DICT[message.chat.id] = list_words

    repeat(message)
    return

if __name__ == '__main__':
    create_database()
    bot.polling()
