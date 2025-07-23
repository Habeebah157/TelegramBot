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

# Patch asyncio for nested loop support
nest_asyncio.apply()

# Load environment variables
load_dotenv()
bot_token = os.environ["BOT_TOKEN"]
URL = os.environ["URL"]
webhook_secret = os.environ.get("WEBHOOK_SECRET", "supersecret")

print("Loaded BOT_TOKEN:", bot_token)

# Configure Telegram Bot with HTTPX
request_config = HTTPXRequest(pool_timeout=10, read_timeout=15, write_timeout=15, connect_timeout=5)
bot = telegram.Bot(token=bot_token, request=request_config)

# Flask app
app = Flask(__name__)

# Function to fetch medium difficulty words from Datamuse API
def get_medium_words():
    try:
        response = requests.get('https://api.datamuse.com/words?sp=??????&md=f&max=100', timeout=5)
        words = response.json()

        def get_freq(word_obj):
            if 'tags' in word_obj:
                for tag in word_obj['tags']:
                    if tag.startswith('f:'):
                        try:
                            return float(tag[2:])
                        except ValueError:
                            return 0
            return 0

        medium_words = [w['word'] for w in words if 700 < get_freq(w) < 10000]

        if not medium_words:
            return ["apple", "banana", "cat", "dog", "elephant", "flower", "guitar", "house"]
        return medium_words
    except Exception as e:
        print(f"Error fetching medium words: {e}")
        return ["apple", "banana", "cat", "dog", "elephant", "flower", "guitar", "house"]

# Function to fetch definition from Free Dictionary API
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

# Function to fetch synonyms from Datamuse API
def get_synonyms(word, max_results=5):
    try:
        response = requests.get(f'https://api.datamuse.com/words?rel_syn={word}&max={max_results}', timeout=5)
        synonyms = response.json()
        return [w['word'] for w in synonyms] if synonyms else []
    except Exception as e:
        print(f"Error fetching synonyms: {e}")
        return []

# Function to fetch antonyms from Datamuse API
def get_antonyms(word, max_results=5):
    try:
        response = requests.get(f'https://api.datamuse.com/words?rel_ant={word}&max={max_results}', timeout=5)
        antonyms = response.json()
        return [w['word'] for w in antonyms] if antonyms else []
    except Exception as e:
        print(f"Error fetching antonyms: {e}")
        return []

# Async function to send messages
async def send_message_async(chat_id, text):
    try:
        print(f"[Worker] Sending message to {chat_id}: {text}")
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=telegram.constants.ParseMode.MARKDOWN)
        print(f"[Worker ✅] Message sent to {chat_id}")
    except Exception as e:
        print(f"[Worker ❌] Failed to send message to {chat_id}: {e}")

# Webhook route
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
            words_list = get_medium_words()
            random_word = random.choice(words_list)
            definition = get_definition(random_word)
            synonyms = get_synonyms(random_word)
            antonyms = get_antonyms(random_word)

            reply = f"**{random_word.capitalize()}**:\n{definition}\n\n"

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

# Manual webhook setup route
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

# Health check
@app.route('/')
def index():
    return 'Bot is running!'

if __name__ == '__main__':
    app.run(threaded=True)
