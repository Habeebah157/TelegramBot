import os
import asyncio
import random
import string
import requests
import urllib.parse

from flask import Flask, request
import telegram
from telegram.request import HTTPXRequest
from urllib.parse import urljoin
from dotenv import load_dotenv
import nest_asyncio

nest_asyncio.apply()
load_dotenv()

bot_token = os.environ["BOT_TOKEN"]
URL = os.environ["URL"]
webhook_secret = os.environ.get("WEBHOOK_SECRET", "supersecret")

request_config = HTTPXRequest(pool_timeout=10, read_timeout=15, write_timeout=15, connect_timeout=5)
bot = telegram.Bot(token=bot_token, request=request_config)

app = Flask(__name__)

def get_low_freq_random_words(n=10, freq_threshold=500):
    words = []
    try:
        for _ in range(n):
            letter = random.choice(string.ascii_lowercase)
            response = requests.get(f'https://api.datamuse.com/words?sp={letter}*&md=f&max=1000', timeout=5)
            data = response.json()
            filtered = [
                w['word'] for w in data
                if 'tags' in w
                for tag in w['tags']
                if tag.startswith('f:') and float(tag[2:]) < freq_threshold
            ]
            if filtered:
                words.append(random.choice(filtered))
            else:
                words.append(random.choice(["arcane", "obscure", "esoteric", "rare", "uncommon"]))
        return words
    except Exception as e:
        print(f"Error fetching low frequency words: {e}")
        return ["arcane", "obscure", "esoteric"]

def get_definition(word):
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            meanings = data[0].get("meanings", [])
            if meanings:
                definitions = meanings[0].get("definitions", [])
                if definitions:
                    return definitions[0].get("definition", "No definition found.")
        return "Sorry, no definition found."
    except Exception as e:
        print(f"Error fetching definition: {e}")
        return "Error fetching definition."

def get_example_sentence(word):
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            meanings = data[0].get("meanings", [])
            for meaning in meanings:
                definitions = meaning.get("definitions", [])
                for definition in definitions:
                    example = definition.get("example")
                    if example:
                        return example
        return None
    except Exception as e:
        print(f"Error fetching example sentence: {e}")
        return None

def get_pronunciation(word):
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            phonetics = data[0].get("phonetics", [])
            for entry in phonetics:
                if "text" in entry:
                    return entry["text"]
        return None
    except Exception as e:
        print(f"Error fetching pronunciation: {e}")
        return None

def get_synonyms(word, max_results=5):
    try:
        response = requests.get(f'https://api.datamuse.com/words?rel_syn={word}&max={max_results}', timeout=5)
        synonyms = response.json()
        return [w['word'] for w in synonyms] if synonyms else []
    except Exception as e:
        print(f"Error fetching synonyms: {e}")
        return []

def get_antonyms(word, max_results=5):
    try:
        response = requests.get(f'https://api.datamuse.com/words?rel_ant={word}&max={max_results}', timeout=5)
        antonyms = response.json()
        return [w['word'] for w in antonyms] if antonyms else []
    except Exception as e:
        print(f"Error fetching antonyms: {e}")
        return []

async def get_audio_pronunciation(word, lang='en'):
    base_url = "https://translate.google.com/translate_tts"
    params = {
        "ie": "UTF-8",
        "q": word,
        "tl": lang,
        "client": "tw-ob"
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"

async def send_message_async(chat_id, text):
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=telegram.constants.ParseMode.MARKDOWN)
    except Exception as e:
        print(f"[❌] Failed to send message: {e}")

async def send_voice_async(chat_id, voice_url):
    try:
        await bot.send_voice(chat_id=chat_id, voice=voice_url)
    except Exception as e:
        print(f"[❌] Failed to send voice: {e}")

@app.route(f'/{webhook_secret}', methods=['POST'])
def respond():
    try:
        update_json = request.get_json(force=True)
        update = telegram.Update.de_json(update_json, bot)

        if not update.message:
            return 'ok', 200

        chat_id = update.message.chat.id
        text = update.message.text or ""

        if text == '/start':
            asyncio.run(send_message_async(chat_id, "Welcome! How can I help you?"))

        elif text == '/word':
            words_list = get_low_freq_random_words()
            random_word = random.choice(words_list)
            definition = get_definition(random_word)
            pronunciation = get_pronunciation(random_word)
            example_sentence = get_example_sentence(random_word)
            synonyms = get_synonyms(random_word)
            antonyms = get_antonyms(random_word)
            audio_url = asyncio.run(get_audio_pronunciation(random_word))

            reply = f"**{random_word.capitalize()}**"
            if pronunciation:
                reply += f" _({pronunciation})_"
            reply += f":\n{definition}\n\n"

            if example_sentence:
                reply += f"_Example:_ {example_sentence}\n\n"

            reply += f"*Synonyms:* {', '.join(synonyms) if synonyms else 'None'}\n"
            reply += f"*Antonyms:* {', '.join(antonyms) if antonyms else 'None'}\n"
            reply += f"\n[🔊 Listen to pronunciation]({audio_url})"

            asyncio.run(send_message_async(chat_id, reply))
            asyncio.run(send_voice_async(chat_id, audio_url))

        else:
            asyncio.run(send_message_async(chat_id, f"You said: {text}"))

        return 'ok', 200

    except Exception as e:
        print("❌ Error in respond():", e)
        return 'ok', 200

@app.route('/set_webhook', methods=['GET'])
def set_webhook_route():
    try:
        webhook_url = urljoin(URL.rstrip('/') + '/', webhook_secret)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(bot.set_webhook(webhook_url))
        loop.close()
        return f"Webhook set: {result}"
    except Exception as e:
        return f"Error setting webhook: {e}"

@app.route('/')
def index():
    return 'Bot is running!'

if __name__ == '__main__':
    app.run(threaded=True)
