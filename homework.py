import logging
import time
import os
import sys

import telegram
import requests
from dotenv import load_dotenv

from exceptions import (SendMessageError, ApiError)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Функция отправки сообщения с состоянием домашней работы."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info('Сообщение отправлено')
    except Exception as error:
        raise SendMessageError(
            logging.error(f'Ошибка при отправке сообщения: {error}')
        )


def get_api_answer(current_timestamp):
    """Делает запрос к сайту и, если ответ корректен, возвращает его."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}  # timestamp - 86400 * 30
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        raise ConnectionError(
            logging.error(f'Ошибка соединения:{error}')
        )
    if response.status_code != 200:
        raise ApiError(
            logging.error('API не вернул ожидаемый результат')
        )
    return response.json()


def check_response(response):
    """Проверка наличия и статуса домашней работы."""
    if not isinstance(response, dict):
        raise TypeError(
            logging.error('Ожидается словарь')
        )
    if 'homeworks' not in response:
        raise KeyError(
            logging.error('Ошибка ключа')
        )
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            logging.error('Ожидается список')
        )
    return response.get('homeworks')


def parse_status(homework):
    """Проверка текущего статуса домашней работы."""
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise ValueError(
            logging.error(
                f'Неизвестный статус домашней работы: {homework_status}'
            )
        )
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность необходимых переменных окружения."""
    if (
        PRACTICUM_TOKEN is None
        or TELEGRAM_TOKEN is None
        or TELEGRAM_CHAT_ID is None
    ):
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise KeyError(logging.critical('Ошибка окружения'))
    logging.debug('Бот запущен!')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            message = parse_status(check_response(response)[0])
            send_message(bot, message)
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message, exc_info=True)
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    log_record = f'{__file__}.log'
    logging.basicConfig(
        handlers=[logging.FileHandler(log_record),
                  logging.StreamHandler(sys.stdout)],
        level=logging.DEBUG,
        format=('%(asctime)s - %(funcName)s - %(lineno)d - '
                '%(levelname)s - %(message)s')
    )
    main()
