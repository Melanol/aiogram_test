import os

from dotenv import load_dotenv, find_dotenv


load_dotenv(find_dotenv())

BOT_API_TOKEN = os.getenv('BOT_API_TOKEN')
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')
