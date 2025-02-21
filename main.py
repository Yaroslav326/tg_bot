import webbrowser
import telebot
import sqlite3
import requests
import json
import uuid
from yookassa import Configuration, Payment
from lxml.html import fromstring
from time import sleep
from config import TOKEN, TOKEN_PAY, ACCOUNT_ID
from bs4 import BeautifulSoup
from datetime import datetime

bot = telebot.TeleBot(TOKEN)


def connect_close_bd(func: object) -> object:
    '''Декоратор открытия  и закрытия базы данных'''

    def wrapper_bd(*args, **kwargs):
        try:
            connect = sqlite3.connect("users.db")
            cursor = connect.cursor()
            db_func = func(cursor, *args, **kwargs)
            connect.commit()

        except Exception as e:
            print(f"An error occurred: {e}")
            connect.rollback()

        finally:
            connect.close()

        return db_func

    return wrapper_bd


@connect_close_bd
def create_db(cursor: object) -> None:
    '''Создание базы данных'''

    cursor.execute('''CREATE TABLE IF NOT EXISTS users(
                    chat_id TEXT NOT NULL,
                    cheque_id TEXT,
                    status TEXT,
                    date DATE)
                    ''')


@connect_close_bd
def insert_db(cursor: object, message: object,
              response={"id": None, "status": None, "created_at": '2018-07-25T10:52:00.233Z'}) -> None:
    '''Добавление данных в базу данных'''

    chat_id = message.chat.id

    cursor.execute(
        'INSERT INTO users(chat_id, cheque_id, status, date) VALUES(?, ?, ?, ?)',
        (chat_id, response["id"], response["status"], response["created_at"]))


@connect_close_bd
def viewing(cursor: object, message: object) -> list:
    '''Запрос на получение последней даты платежа'''

    chat_id = message.chat.id

    cursor.execute('SELECT chat_id FROM users WHERE chat_id = ?', (chat_id,))
    user_exists = cursor.fetchone()

    if user_exists is None:
        insert_db(message)

    cursor.execute('SELECT MAX(date) FROM users WHERE chat_id = ?', (chat_id,))
    users_date_payment = cursor.fetchone()

    if users_date_payment and users_date_payment[0] is not None:
        return users_date_payment[0]
    else:
        return None


def creating_payment(message: object) -> None:
    '''Функция оплаты'''

    Configuration.account_id = ACCOUNT_ID
    Configuration.secret_key = TOKEN_PAY

    idempotence_key = str(uuid.uuid4())
    payment = Payment.create({
        "amount": {
            "value": "1.00",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "https://web.telegram.org/a/#7927671455"
        },
        "capture": True,
        "description": "Заказ на подписку"
    }, idempotence_key)

    confirmation_url = payment.confirmation.confirmation_url
    webbrowser.open(confirmation_url)

    payment_data = json.loads(payment.json())
    payment_id = payment_data['id']

    payment = json.loads((Payment.find_one(payment_id)).json())

    while payment['status'] == 'pending':
        payment = json.loads((Payment.find_one(payment_id)).json())
        sleep(10)

    if payment['status'] == 'succeeded':
        insert_db(message, payment)


def data_requests() -> list:
    """Запрос цен валют"""

    data = requests.get("https://www.cbr-xml-daily.ru/daily_json.js").text
    return json.loads(data)


@bot.message_handler(commands=['start'])
def start_bot(message: object) -> None:
    """Стартовая страница, создаем кнопки для выбора дальнейших действий"""

    chat_id = message.chat.id
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard_reply = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_start = telebot.types.KeyboardButton(text='/start')
    button_notice = telebot.types.InlineKeyboardButton(text='Уведомление', callback_data='price_notice')
    button_price = telebot.types.InlineKeyboardButton(text='Просмотр стоимости', callback_data='price_viewing')
    button_news = telebot.types.InlineKeyboardButton(text='Просмотр новостей', callback_data='news_viewing')
    keyboard_reply.add(button_start)
    keyboard.add(button_notice)
    keyboard.add(button_price)
    keyboard.add(button_news)
    bot.send_message(chat_id, 'Выберите действие', reply_markup=keyboard)
    bot.send_message(chat_id, 'Для обновления меню нажмите start', reply_markup=keyboard_reply)


@bot.callback_query_handler(func=lambda call: call.data == 'price_notice')
def price_notice(call: object) -> None:
    """ Функция для оповещения о достижения установленной цены """

    message = call.message
    chat_id = message.chat.id
    message_id = message.message_id
    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='Введите тикет валюты')
    bot.register_next_step_handler(message, select_prais)


def select_prais(message: object) ->None:
    """Выбор желаемой цены"""

    chat_id = message.chat.id
    ticket = message.text.strip().upper()
    data = data_requests()
    data_payment = viewing(message)

    if data_payment is None:
        data_payment = viewing(message)

    delta_data = datetime.now() - datetime.strptime(data_payment, "%Y-%m-%dT%H:%M:%S.%fZ")

    if delta_data.total_seconds() <= 2678400:

        if ticket in data['Valute']:
            bot.send_message(chat_id, 'Введите ожидаемую цену')
            bot.register_next_step_handler(message, tracking, ticket)

        else:
            bot.send_message(chat_id, "Некорректный тикет. Пожалуйста, попробуйте снова.")

    elif delta_data.total_seconds() > 2678400:
        bot.send_message(chat_id, 'Произведите оплату')
        creating_payment(message)


def tracking(message: object, ticket: str) -> None:
    """Отслеживание цены"""

    ticket = ticket
    data = data_requests()
    prais = message.text.strip().upper()
    dictionary_ticket = {ticket: float(prais)}

    if dictionary_ticket[ticket] < data['Valute'][ticket]['Value']:
        upp_tracking(message, ticket, dictionary_ticket)

    else:
        lower_tracking(message, ticket, dictionary_ticket)


def upp_tracking(message: object, ticket: str, dictionary_ticket: dict) ->None:
    """Отслеживание повышения цены"""

    dictionary_ticket = dictionary_ticket
    chat_id = message.chat.id

    while dictionary_ticket:
        data = data_requests()
        sleep(1)

        for i in list(dictionary_ticket.keys()):
            if data['Valute'][ticket]['Value'] <= dictionary_ticket[i]:
                bot.send_message(chat_id, f"{data['Valute'][ticket]['Name']} достиг значения {dictionary_ticket[i]}")
                del dictionary_ticket[i]

                if not dictionary_ticket:
                    break


def lower_tracking(message: object, ticket: str, dictionary_ticket: dict) -> None:
    """Отслеживание понижения цены"""

    dictionary_ticket = dictionary_ticket
    chat_id = message.chat.id

    while dictionary_ticket:
        data = data_requests()
        sleep(1)

        for i in list(dictionary_ticket.keys()):
            if data['Valute'][ticket]['Value'] >= dictionary_ticket[i]:
                bot.send_message(chat_id, f"{data['Valute'][ticket]['Name']} достиг значения {dictionary_ticket[i]}")
                del dictionary_ticket[i]

                if not dictionary_ticket:
                    break


@bot.callback_query_handler(func=lambda call: call.data == 'price_viewing')
def price_viewing(call):
    """Функция для просмотра курса волют по введеному тикету"""

    message = call.message
    chat_id = message.chat.id
    message_id = message.message_id
    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text='Введите тикет валюты')
    bot.register_next_step_handler(message, process_ticket)


def process_ticket(message: object) -> None:
    """Запрашиваем у функции data_requests текущий курс"""

    chat_id = message.chat.id
    ticket = message.text.strip().upper()
    data = data_requests()

    if ticket in data['Valute']:
        bot.send_message(chat_id, f"{data['Valute'][ticket]['Nominal']} "
                                  f"{data['Valute'][ticket]['Name']} равен "
                                  f"{data['Valute'][ticket]['Value']}")
    else:
        bot.send_message(chat_id, "Некорректный тикет. Пожалуйста, попробуйте снова.")


@bot.callback_query_handler(func=lambda call: call.data == 'news_viewing')
def news_viewing(call: object) -> None:
    '''Запрос на получение новостей'''

    message = call.message
    chat_id = message.chat.id
    message_id = message.message_id
    url_news = ('https://quote.ru/news/article/67ac5a389a7947d2cd5655be')
    response = requests.get(url_news)
    bs = BeautifulSoup(response.text, "lxml")
    news = bs.find_all('p')
    news = ' '.join([p.get_text() for p in news])
    parser_obj = fromstring(news)
    output_string = str(parser_obj.text_content())
    bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=output_string)


if __name__ == '__main__':
    print('Бот запущен!')
    create_db()
    bot.infinity_polling()
