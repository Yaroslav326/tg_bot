import sqlite3
import telebot
from typing import Callable

def connect_close_bd(func: Callable) -> Callable:
    '''
    Декоратор `connect_close_bd` открывает соединение с базой данных перед
    выполнением функции и закрывает его после завершения работы функции.

    Данный декоратор используется для управления соединением с базой данных
    SQLite. Он автоматически открывает соединение, передает курсор в
    декорируемую функцию, а также обрабатывает исключения, обеспечивая
    корректное закрытие соединения и откат транзакции в случае ошибки.

    Args:
    func (Callable):
        Декорируемая функция, которая будет выполнена с открытым
        соединением к базе данных.

    Returns:
    Callable:
        Возвращает обернутую функцию, которая будет выполнять операции с базой
        данных.
    '''

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
def create_db(cursor: sqlite3.Cursor) -> None:
    '''
    Функция `create_db` создает таблицу пользователей в базе данных.

    Данная функция используется для создания таблицы `users`, если она еще не
    существует. Таблица содержит информацию о пользователях, включая их
    идентификаторы чата, идентификаторы чеков, статусы и даты платежей.

    Args:
        cursor (sqlite3.Cursor):
        Курсор для выполнения SQL-запросов к базе данных.

    Returns:
        None:
    '''

    cursor.execute('''CREATE TABLE IF NOT EXISTS users(
                    chat_id TEXT NOT NULL,
                    cheque_id TEXT,
                    status TEXT,
                    date DATE)
                    ''')


@connect_close_bd
def insert_db(cursor: sqlite3.Cursor, message: telebot.types.Message,
              response={'id': None, 'status': None,
                        'created_at': '2018-07-25T10:52:00.233Z'}) -> None:

    '''
    Функция `insert_db` добавляет данные о пользователе в базу данных.

    Данная функция используется для добавления записи о пользователе в таблицу
    `users`. Если ответ от платежной системы не был передан, используется
    значение по умолчанию. Функция получает идентификатор чата из сообщения и
    сохраняет информацию о платеже.

    Args:
        cursor (sqlite3.Cursor):
        Курсор для выполнения SQL-запросов к базе данных.
        message (telebot.types.Message):
        Сообщение от пользователя, содержащее информацию о платеже.
        Используется для получения идентификатора чата
        response (dict, optional):
        Словарь с данными о платеже, включая идентификатор, статус и
        дату создания.
        По умолчанию равен {'id': None, 'status': None,
        'created_at': '2018-07-25T10:52:00.233Z'}

    Returns:
        None:
    '''

    if response is None:
        response = {'id': None, 'status': None,
                    'created_at': '2018-07-25T10:52:00.233Z'}
    chat_id = message.chat.id

    cursor.execute(
        '''INSERT INTO users(chat_id, cheque_id, status, date)
           VALUES (?, ?, ?, ?)''',
        (chat_id, response["id"], response['status'],
         response['created_at']))



@connect_close_bd
def viewing(cursor: object, message: telebot.types.Message) -> list:
    '''
    Функция `viewing` запрашивает последнюю дату платежа пользователя

    Данная функция используется для получения последней даты платежа
    пользователя из таблицы `users`. Если пользователь не найден, функция
    добавляет его в базу данных. Возвращает максимальную дату платежа для
    данного пользователя.

    Args:
        cursor (object):
        Курсор для выполнения SQL-запросов к базе данных.
        message (telebot.types.Message):
        Сообщение от пользователя, содержащее информацию о платеже.
        Используется для получения идентификатора чата.

    Returns:
        list:
        Возвращает последнюю дату платежа для данного пользователя или
        None, если данных нет.
    '''

    chat_id = message.chat.id

    cursor.execute('SELECT chat_id FROM users WHERE chat_id = ?', (chat_id,))
    user_exists = cursor.fetchone()

    if user_exists is None:
        insert_db(message)

    cursor.execute('SELECT MAX(date) FROM users WHERE chat_id = ?', (chat_id,))
    users_date_payment = cursor.fetchone()

    if users_date_payment and users_date_payment[0] is not None:
        return users_date_payment[0]
