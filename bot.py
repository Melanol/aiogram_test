import datetime
import logging
import random
import re

from aiogram.types.message import ContentType
from aiogram.utils.markdown import text, bold, italic, code, pre
from aiogram.types import ParseMode, InputMediaPhoto, InputMediaVideo, ChatActions
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
import requests

from config import BOT_API_TOKEN, WEATHER_API_KEY


logging.basicConfig(format=u'%(filename)s [ LINE:%(lineno)+3s ]#%(levelname)+8s [%(asctime)s]  %(message)s',
                    level=logging.INFO)


bot = Bot(token=BOT_API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


@dp.message_handler(commands=['start'])
async def process_start_command(message: types.Message):
    """Greets the user."""
    await message.answer('Hello there. Type /help to get the list of commands.')


@dp.message_handler(state='*', commands='cancel')
async def cancel_handler(message: types.Message, state: FSMContext):
    """Cancels input."""
    current_state = await state.get_state()
    if current_state is None:
        return

    logging.info('Cancelling state %r', current_state)
    await state.finish()
    # Remove keyboard (just in case)
    await message.answer('Cancelled.', reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(commands=['help'])
async def process_help_command(message: types.Message):
    """Informs the user of available commands."""
    msg = text(bold('Available commands:'), '/start', '/help', '/weather', '/exchange', '/cute', '/poll', sep='\n')
    await message.answer(msg, parse_mode=ParseMode.MARKDOWN)


class WeatherForm(StatesGroup):
    location = State()


@dp.message_handler(commands=['weather'])
async def process_weather_command(message: types.Message):
    """Initiates getting weather data."""
    await WeatherForm.location.set()
    await message.answer("Enter location name.")


@dp.message_handler(state=WeatherForm.location)
async def process_exchange_data(message: types.Message, state: FSMContext):
    """Processing location."""
    async with state.proxy() as data:
        data['location'] = message.text
        url = f'https://api.openweathermap.org/data/2.5/weather?q={data["location"]}&appid={WEATHER_API_KEY}' \
              f'&units=metric'
        response = requests.get(url)
        json_data = response.json()
        if json_data["cod"] == 200:  # If there is no error
            await message.answer(f'Weather in {json_data["name"]}, {json_data["sys"]["country"]}: '
                                 f'{json_data["weather"][0]["description"]}, temp: {json_data["main"]["temp"]}, '
                                 f'feels like: {json_data["main"]["feels_like"]}, wind: {json_data["wind"]["speed"]}.')
        else:  # Send the user error data
            await message.answer(f'{json_data["cod"]} {json_data["message"]}')

        await state.finish()


class ExchangeForm(StatesGroup):
    exchange_data = State()


@dp.message_handler(commands=['exchange'])
async def process_exchange_command(message: types.Message):
    """Initiates getting currency exchange data."""
    await ExchangeForm.exchange_data.set()
    await message.answer("Enter from currency and to currency separated by space.")


@dp.message_handler(lambda message: not bool(re.match(r'^[A-Z]{3} [A-Z]{3}$', message.text.upper())),
                    state=ExchangeForm.exchange_data)
async def process_exchange_data_invalid(message: types.Message):
    """Checking exchange_data."""
    return await message.answer('Invalid query. Example: "USD EUR".')


@dp.message_handler(state=ExchangeForm.exchange_data)
async def process_exchange_data(message: types.Message, state: FSMContext):
    """Processing exchange_data."""
    async with state.proxy() as data:
        data['exchange_data'] = message.text
        from_, to = data['exchange_data'].upper().split()
        url = f'https://api.exchangerate.host/convert?from={from_}&to={to}'
        response = requests.get(url)
        json_data = response.json()
        await message.answer(f'{from_} to {to}: {json_data["info"]["rate"]}.')
        await state.finish()


@dp.message_handler(commands=['cute'])
async def process_cute_command(message: types.Message):
    """Sends a picture of a cute animal."""
    caption = "Here is your cutie."
    choice = random.choice(['cat', 'dog'])
    if choice == 'cat':  # Warning: Sometimes the cat server is unavailable or takes too long
        timestamp = datetime.datetime.now().isoformat()  # Needed to stop images from caching and sending the same image
        await bot.send_photo(message.from_user.id, photo=f'https://cataas.com/cat/cute?a={timestamp}', caption=caption)
    elif choice == 'dog':
        url = "https://random.dog/woof.json"
        response = requests.get(url)
        json_data = response.json()
        await bot.send_photo(message.from_user.id, photo=json_data["url"], caption=caption)


class PollForm(StatesGroup):
    group_chat_id = State()
    question = State()
    options = State()


@dp.message_handler(commands=['poll'])
async def process_poll_command(message: types.Message):
    """Initiates creating a poll."""
    await PollForm.group_chat_id.set()
    await message.answer("Creating a poll for a group chat. "
                         "State a group chat ID (example: -912691444; don't forget to invite the bot to the chat).")


@dp.message_handler(lambda message: not bool(re.match(r'^-\d+$', message.text)), state=PollForm.group_chat_id)
async def process_group_chat_id_invalid(message: types.Message):
    """Checking group_chat_id."""
    return await message.answer("Invalid group chat ID. Example: -912691444. "
                                "Don't forget to invite the bot to the chat.")


@dp.message_handler(state=PollForm.group_chat_id)
async def process_group_chat_id(message: types.Message, state: FSMContext):
    """Processing group_chat_id."""
    async with state.proxy() as data:
        data['group_chat_id'] = message.text

    await PollForm.next()
    await message.answer("State a question.")


@dp.message_handler(state=PollForm.question)
async def process_question(message: types.Message, state: FSMContext):
    """Processing question."""
    async with state.proxy() as data:
        data['question'] = message.text

    await PollForm.next()
    await message.answer('State options. Separate them by a semicolon and a space.')


@dp.message_handler(lambda message: not bool(re.search(r'\w; \w', message.text)), state=PollForm.options)
async def process_options_invalid(message: types.Message):
    """Checking options."""
    return await message.answer('At least 2 options are required. Separate them by a semicolon and a space.')


@dp.message_handler(state=PollForm.options)
async def process_options(message: types.Message, state: FSMContext):
    """Processing options."""
    async with state.proxy() as data:
        data['options'] = message.text.split(';')
        await bot.send_poll(chat_id=data['group_chat_id'],
                            question=data['question'],
                            options=data['options'])

        await message.answer("Poll sent to the group chat " + data['group_chat_id'])

    await state.finish()


@dp.message_handler(content_types=ContentType.ANY)
async def unknown_message(msg: types.Message):
    """Processing unexpected input."""
    message_text = text('Invalid entry. Use /help')
    await msg.answer(message_text, parse_mode=ParseMode.MARKDOWN)


if __name__ == '__main__':
    executor.start_polling(dp)
