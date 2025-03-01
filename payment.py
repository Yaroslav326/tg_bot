import telebot
import uuid
import webbrowser
import json
from time import sleep
from yookassa import Configuration, Payment
from config import TOKEN_PAY, ACCOUNT_ID
from bd import insert_db


def creating_payment(message: telebot.types.Message) -> None:
    '''Функция оплаты'''

    Configuration.account_id = ACCOUNT_ID
    Configuration.secret_key = TOKEN_PAY

    idempotence_key = str(uuid.uuid4())
    payment = Payment.create({
        'amount': {
            'value': '1.00',
            'currency': 'RUB'
        },
        'confirmation': {
            'type': 'redirect',
            'return_url': 'https://web.telegram.org/a/#7927671455'
        },
        'capture': True,
        'description': 'Заказ на подписку'
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
