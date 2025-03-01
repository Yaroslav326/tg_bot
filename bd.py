import sqlite3
import telebot
from typing import Callable

def connect_close_bd(func: Callable) -> Callable:
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
def create_db(cursor: sqlite3.Cursor) -> None:
    '''Создание базы данных'''

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

    '''Добавление данных в базу данных'''

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
