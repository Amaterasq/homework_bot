import logging
import time
import os
import sys

import telegram
import requests
from dotenv import load_dotenv

from exceptions import (ApiError, ResponseError)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

TOKENS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')


RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

START_BOT = 'Бот запущен!'
SEND_MESSAGE = 'Сообщение отправлено: {message} .'
ERROR_ENV = 'Ошибка окружения'
ERROR_SEND_MESSAGE = 'Ошибка при отправке сообщения: {error}'
ERROR_CONNECT = ('Ошибка соединения: {error}. Момент времени - {params}, '
                 'токен - {headers}, API - {url}')
ERROR_API = ('API не вернул ожидаемый результат, получен статус: {status} '
             'Момент времени - {params}, токен - {headers}, API - {url}')
ERROR_IN_RESPONSE = ('API вернул ответ с ошибкой {error}. '
                     'Текст ошибки: {error_text} '
                     'API - {url}, токен - {headers}, '
                     'Момент времени - {params}')
UNKNOWN_STATUS = 'Неизвестный статус домашней работы: {status}'
ERROR_NO_DICT = 'Ожидается тип "dict", получено: {type}'
ERROR_NO_LIST = 'Ожидается тип "list", получено: {type}'
ERROR_NO_KEY = 'Ключа "homeworks" нет в ответе {response}'
CHANGE_HOMEWORK_STATUS = 'Изменился статус проверки работы "{name}". {verdict}'
MISSING_TOKENS = 'Пропущены токены: {token}'
NO_CHANGE_HOMEWORK_STATUS = 'Статус работы не изменился'
FINAL_LOG = 'Ошибка в работе программы: {error}'


def send_message(bot, message):
    """Функция отправки сообщения с состоянием домашней работы."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(SEND_MESSAGE.format(message=message))
    except Exception as error:
        logging.exception(ERROR_SEND_MESSAGE.format(error=error))


def get_api_answer(timestamp):
    """Делает запрос к сайту и, если ответ корректен, возвращает его."""
    # params = {'from_date': timestamp}  # timestamp - 86400 * 30
    params = dict(
        url=ENDPOINT,
        headers=HEADERS,
        params={'from_date': timestamp}
    )
    try:
        response = requests.get(**params)
    except requests.RequestException as error:
        raise ConnectionError(
            ERROR_CONNECT.format(error=error, **params)
        )
    if response.status_code != 200:
        raise ApiError(
            ERROR_API.format(response=response.status_code, **params)
        )
    response = response.json()
    for error in ('error', 'code'):
        if error in response:
            raise ResponseError(
                ERROR_IN_RESPONSE.format(
                    error=error, error_text=response[error], **params
                )
            )
    return response


def check_response(response):
    """Проверка наличия и статуса домашней работы."""
    if not isinstance(response, dict):
        raise TypeError(ERROR_NO_DICT.format(type=type(response)))
    if 'homeworks' not in response:
        raise KeyError(ERROR_NO_KEY.format(response=response))
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            ERROR_NO_LIST.format(type=type(response['homeworks']))
        )
    return response.get('homeworks')


def parse_status(homework):
    """Проверка текущего статуса домашней работы."""
    status = homework['status']
    if status not in VERDICTS:
        raise ValueError(
            UNKNOWN_STATUS.format(status)
        )
    return CHANGE_HOMEWORK_STATUS.format(
        name=homework.get('homework_name'),
        verdict=VERDICTS.get(status)
    )


def check_tokens():
    """Проверка наличия переменых окружения."""
    missing_tokens = [
        logging.critical(MISSING_TOKENS.format(token=token))
        for token in TOKENS if globals()[token] is None
    ]
    if missing_tokens:
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise KeyError(ERROR_ENV)
    logging.debug(START_BOT)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    previous_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            message = parse_status(check_response(response)[0])
            if message != previous_message:
                send_message(bot, message)
                previous_message = message
            else:
                logging.debug(NO_CHANGE_HOMEWORK_STATUS)
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = FINAL_LOG.format(error=error)
            send_message(bot, message)
            logging.exception(message)
        finally:
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
