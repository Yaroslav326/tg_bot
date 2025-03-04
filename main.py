import telebot
import requests
import json
from lxml.html import fromstring
from time import sleep
from config import TOKEN
from bs4 import BeautifulSoup
from datetime import datetime
from bd import create_db, viewing
from payment import creating_payment

bot = telebot.TeleBot(TOKEN)
URI_NEWS = 'https://quote.ru/news/article/67ac5a389a7947d2cd5655be'
URL_PRAIS = 'https://www.cbr-xml-daily.ru/daily_json.js'


def data_requests() -> list:
    """
    Функция `data_requests` запрашивает актуальные цены валют

    Данная функция используется для получения данных о курсах валют в формате
    JSON. Она отправляет HTTP-запрос к API Центрального банка России и
    возвращает расшифрованные данные в виде списка

    Args:
        None:

    Returns:
        list:
        Возвращает список с данными о курсах валют
    """

    data = requests.get(URL_PRAIS).text
    return json.loads(data)


@bot.message_handler(commands=['start'])
def start_bot(message: telebot.types.Message) -> None:
    """"
    Функция `start_bot` обрабатывает команду `/start` и создает интерфейс для
    взаимодействия с пользователем

    Данная функция используется для инициализации бота и отображения стартового
    меню с кнопками, позволяющими пользователю выбрать дальнейшие действия.
    Она создает как встроенные, так и обычные кнопки, которые позволяют
    взаимодействовать с ботом и получать доступ к различным функциям.

    Args:
    message (telebot.types.Message):
        Сообщение от пользователя, содержащие информацию о чате, в
        котором будет отправлено меню

    Returns:
        None:
    """

    chat_id = message.chat.id
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard_reply = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    button_start = telebot.types.KeyboardButton(text='/start')
    button_notice = telebot.types.InlineKeyboardButton(
                                                        text= \
                                                            'Уведомление',
                                                        callback_data= \
                                                            'price_notice'
                                                        )
    button_price = telebot.types.InlineKeyboardButton(
                                                     text= \
                                                         'Просмотр стоимости',
                                                     callback_data= \
                                                          'price_viewing'
                                                     )
    button_news = telebot.types.InlineKeyboardButton(
                                                    text= \
                                                        'Просмотр новостей',
                                                    callback_data= \
                                                        'news_viewing'
                                                    )
    keyboard_reply.add(button_start)
    keyboard.add(button_notice)
    keyboard.add(button_price)
    keyboard.add(button_news)
    bot.send_message(chat_id, 'Выберите действие', reply_markup=keyboard)
    bot.send_message(chat_id, 'Для обновления меню нажмите start',
                     reply_markup=keyboard_reply)


@bot.callback_query_handler(func=lambda call: call.data == 'price_notice')
def price_notice(call: telebot.types.CallbackQuery) -> None:
    """
    Функция `price_notice` обрабатывает запрос на установку уведомления о
    достижении установленной цены валюты

    Данная функция используется для изменения текста сообщения и запроса у
    пользователя тикета валюты, по которому он хочет получать уведомления о
    ценах. Она редактирует предыдущее сообщение и регистрирует следующий шаг,
    который будет обрабатывать введенные данные.

    Args:
        call (telebot.types.CallbackQuery):
        Объект обратного вызова, содержащий информацию о нажатой кнопке и чате,
        в котором нужно отправить сообщение.

    Returns:
        None:
    """

    message = call.message
    chat_id = message.chat.id
    message_id = message.message_id
    bot.edit_message_text(chat_id=chat_id,
                          message_id=message_id,
                          text='Введите тикет валюты')
    bot.register_next_step_handler(message, select_prais)


def select_prais(message: telebot.types.Message) -> None:
    """
    Функция `select_prais` обрабатывает выбор пользователем тикета валюты и
    ожидаемой цены.

    Данная функция используется для получения тикета валюты от пользователя и
    проверки его корректности. Если тикет валиден, пользователь будет запрошен
    о вводе ожидаемой цены. Функция также проверяет, была ли произведена
    оплата, и если нет, предлагает пользователю произвести оплату. В случае,
    если тикет неверный, пользователю будет предложено попробовать снова.

    Args:
    message (telebot.types.Message):
        Сообщение от пользователя, содержащее тикет валюты и информацию о чате.

    Returns:
        None:
    """

    chat_id = message.chat.id
    ticket = message.text.strip().upper()
    data = data_requests()
    data_payment = viewing(message)

    if data_payment is None:
        data_payment = viewing(message)

    delta_data = datetime.now() - datetime.strptime(
        data_payment,
        "%Y-%m-%dT%H:%M:%S.%fZ")

    if delta_data.total_seconds() <= 2678400:

        if ticket in data['Valute']:
            bot.send_message(chat_id, 'Введите ожидаемую цену')
            bot.register_next_step_handler(message, tracking, ticket)

        else:
            bot.send_message(chat_id,
                             "Некорректный тикет. Пожалуйста, "
                             "попробуйте снова.")

    elif delta_data.total_seconds() > 2678400:
        bot.send_message(chat_id, 'Произведите оплату')
        creating_payment(message)


def tracking(message: telebot.types.Message, ticket: str) -> None:
    """
    Функция `tracking` отслеживает изменения цены выбранной валюты.

    Данная функция используется для отслеживания изменения цены валюты,
    введенной пользователем. Она сравнивает ожидаемую цену с текущей ценой и
    вызывает соответствующую функцию для отслеживания повышения или
    понижения цены.

    Args:
        message (telebot.types.Message):
        Сообщение от пользователя, содержащее ожидаемую цену.
        ticket (str):
        Тикет валюты, для которой будет осуществляться отслеживание.

    Returns:
        None:
    """

    ticket = ticket
    data = data_requests()
    prais = message.text.strip().upper()
    dictionary_ticket = {ticket: float(prais)}

    if dictionary_ticket[ticket] < data['Valute'][ticket]['Value']:
        upp_tracking(message, ticket, dictionary_ticket)

    else:
        lower_tracking(message, ticket, dictionary_ticket)


def upp_tracking(message: telebot.types.Message, ticket: str,
                 dictionary_ticket: dict) -> None:
    """
    Функция `upp_tracking` отслеживает повышение цены валюты.

    Данная функция используется для мониторинга повышения цены валюты,
    введенной пользователем. Она периодически запрашивает актуальные данные
    о ценах и уведомляет пользователя, когда цена достигает или превышает
    ожидаемую.

    Args:
        message (telebot.types.Message):
        Сообщение от пользователя, содержащее информацию о чате.
        ticket (str):
        Тикет валюты, для которой осуществляется отслеживание повышения цены.
        dictionary_ticket (dict):
        Словарь, содержащий тикет валюты и ожидаемую цену.

    Returns:
        None:
    """

    dictionary_ticket = dictionary_ticket
    chat_id = message.chat.id

    while dictionary_ticket:
        data = data_requests()
        sleep(1)

        for i in list(dictionary_ticket.keys()):
            if data['Valute'][ticket]['Value'] <= dictionary_ticket[i]:
                bot.send_message(chat_id,
                                 f"{data['Valute'][ticket]['Name']} "
                                 f"достиг значения {dictionary_ticket[i]}")
                del dictionary_ticket[i]

                if not dictionary_ticket:
                    break


def lower_tracking(message: telebot.types.Message, ticket: str,
                   dictionary_ticket: dict) -> None:
    """
    Функция `lower_tracking` отслеживает понижение цены валюты.

    Данная функция используется для мониторинга понижения цены валюты,
    введенной пользователем. Она периодически запрашивает актуальные данные о
    ценах и уведомляет пользователя, когда цена достигает или опускается
    ниже ожидаемой.

    Args:
        message (telebot.types.Message):
        Сообщение от пользователя, содержащее информацию о чате.
        ticket (str):
        Тикет валюты, для которой осуществляется отслеживание понижения цены.
        dictionary_ticket (dict):
        Словарь, содержащий тикет валюты и ожидаемую цену.

    Returns:
        None:
    """
    dictionary_ticket = dictionary_ticket
    chat_id = message.chat.id

    while dictionary_ticket:
        data = data_requests()
        sleep(1)

        for i in list(dictionary_ticket.keys()):
            if data['Valute'][ticket]['Value'] >= dictionary_ticket[i]:
                bot.send_message(chat_id,
                                 f"{data['Valute'][ticket]['Name']} "
                                 f"достиг значения {dictionary_ticket[i]}")
                del dictionary_ticket[i]

                if not dictionary_ticket:
                    break


@bot.callback_query_handler(func=lambda call: call.data == 'price_viewing')
def price_viewing(call: telebot.types.CallbackQuery) -> None:
    """
    Функция price_viewing используется для просмотра текушей цены указанной
    валюты

    Данная функция используется для используется для просмотра текушей цены
    указанной валюты введенной пользователем. Она запрашивает у пользователя
    данные о какой валюте необходимо получить информацию и вызывает функцию
    которая обработку запроса

    Args:
        call (telebot.types.CallbackQuery):
        Объект обратного вызова, содержащий информацию о нажатой кнопке и чате,
        в котором нужно отправить сообщение.

    Returns:
        None:
    """

    message = call.message
    chat_id = message.chat.id
    message_id = message.message_id
    bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                          text='Введите тикет валюты')
    bot.register_next_step_handler(message, process_ticket)


def process_ticket(message: telebot.types.Message) -> None:
    """
    Функция process_ticket используется для получения текушей цены указанной
    валюты

    Данная функция используется для используется для просмотра текушей цены
    указанной валюты введенной пользователем. Она вызывает функцию
    data_requests и из полученного дынных выбирает дынные о запрошенной валюте,
    которые выводит пользавателю

    Args:
        call (telebot.types.CallbackQuery):
        Объект обратного вызова, содержащий информацию о нажатой кнопке и чате,
        в котором нужно отправить сообщение.

    Returns:
        None:
    """

    chat_id = message.chat.id
    ticket = message.text.strip().upper()
    data = data_requests()

    if ticket in data['Valute']:
        bot.send_message(chat_id, f"{data['Valute'][ticket]['Nominal']} "
                                  f"{data['Valute'][ticket]['Name']} равен "
                                  f"{data['Valute'][ticket]['Value']}")
    else:
        bot.send_message(chat_id, "Некорректный тикет. "
                                  "Пожалуйста, попробуйте снова.")


@bot.callback_query_handler(func=lambda call: call.data == 'news_viewing')
def news_viewing(call: telebot.types.CallbackQuery) -> None:
    """
    Функция news_viewing запрашивает новости

    Данная функция используется для получения данных о новостях валютного рынка
    Она выполняет парсинг новостного сайта и отправляет пользователю
    сообшение с последними новостями

    Args:
        call (telebot.types.CallbackQuery):
        Объект обратного вызова, содержащий информацию о нажатой кнопке и чате,
        в котором нужно отправить сообщение.

    Returns:
    """

    message = call.message
    chat_id = message.chat.id
    message_id = message.message_id
    response = requests.get(URI_NEWS)
    bs = BeautifulSoup(response.text, "lxml")
    news = bs.find_all('p')
    news = ' '.join([p.get_text() for p in news])
    parser_obj = fromstring(news)
    output_string = str(parser_obj.text_content())
    bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                          text=output_string)


if __name__ == '__main__':
    print('Бот запущен!')
    create_db()
    bot.infinity_polling()
