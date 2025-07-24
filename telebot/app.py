import os
import asyncio
import random
import requests
from flask import Flask, request
import telegram
from telegram.request import HTTPXRequest
from urllib.parse import urljoin
from dotenv import load_dotenv
import nest_asyncio

nest_asyncio.apply()  # Allows running asyncio tasks inside running event loops without errors

load_dotenv()
bot_token = os.environ["BOT_TOKEN"]
URL = os.environ["URL"]
webhook_secret = os.environ.get("WEBHOOK_SECRET", "supersecret")

request_config = HTTPXRequest(pool_timeout=10, read_timeout=15, write_timeout=15, connect_timeout=5)
bot = telegram.Bot(token=bot_token, request=request_config)

app = Flask(__name__)

def get_medium_adjectives():
    try:
        response = requests.get('https://api.datamuse.com/words?sp=a*&md=pf&max=1000', timeout=5)
        words = response.json()
        print("Fetched words from API:", len(words))

        def get_freq(word_obj):
            if 'tags' in word_obj:
                for tag in word_obj['tags']:
                    if tag.startswith('f:'):
                        try:
                            return float(tag[2:])
                        except ValueError:
                            return 0
            return 0

        def is_adjective(word_obj):
            return 'tags' in word_obj and 'adj' in word_obj['tags']

        medium_adjectives = [
            w['word'] for w in words
            if is_adjective(w) and 700 < get_freq(w) < 10000
        ]

        if not medium_adjectives:
            return [
                "intermediate", "moderate", "subtle", "robust", "complex",
                "steady", "dynamic", "vivid", "precise", "refined"
            ]

        return medium_adjectives

    except Exception as e:
        print(f"Error fetching medium adjectives: {e}")
        return [
            "intermediate", "moderate", "subtle", "robust", "complex",
            "steady", "dynamic", "vivid", "precise", "refined"
        ]

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

async def send_message_async(chat_id, text):
    try:
        print(f"[Worker] Sending message to {chat_id}: {text}")
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=telegram.constants.ParseMode.MARKDOWN)
        print(f"[Worker ✅] Message sent to {chat_id}")
    except Exception as e:
        print(f"[Worker ❌] Failed to send message to {chat_id}: {e}")

@app.route(f'/{webhook_secret}', methods=['POST'])
def respond():
    try:
        update_json = request.get_json(force=True)
        update = telegram.Update.de_json(update_json, bot)

        if not update.message:
            print("[Webhook] No message in update.")
            return 'ok', 200

        chat_id = update.message.chat.id
        text = update.message.text or ""
        print(f"[Webhook] Received message from {chat_id}: {text}")

        if text == '/start':
            asyncio.run(send_message_async(chat_id, "Welcome! How can I help you?"))

        elif text == '/word':
            words_list = get_medium_adjectives()
            random_word = random.choice(words_list)
            definition = get_definition(random_word)
            pronunciation = get_pronunciation(random_word)
            example_sentence = get_example_sentence(random_word)
            synonyms = get_synonyms(random_word)
            antonyms = get_antonyms(random_word)

            reply = f"**{random_word.capitalize()}**"

            if pronunciation:
                reply += f" _({pronunciation})_"

            reply += f":\n{definition}\n\n"

            if example_sentence:
                reply += f"_Example:_ {example_sentence}\n\n"

            if synonyms:
                reply += f"*Synonyms:* {', '.join(synonyms)}\n"
            else:
                reply += "*Synonyms:* None found\n"

            if antonyms:
                reply += f"*Antonyms:* {', '.join(antonyms)}"
            else:
                reply += "*Antonyms:* None found"

            asyncio.run(send_message_async(chat_id, reply))

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
        print(f"Setting webhook to: {webhook_url}")

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
