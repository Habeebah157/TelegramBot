import os
import sys
import threading
import asyncio
from flask import Flask, request
import telegram
from telegram.request import HTTPXRequest
import redis
from rq import Queue

# Add credentials path and import your tokens here
sys.path.append(os.path.join(os.path.dirname(__file__), 'telegram-bot', 'credentials'))
from credentials import BOT_TOKEN, URL,REDIS_URL  # Adjust this import path as needed

bot_token = BOT_TOKEN
URL = URL or "https://telegrambot-mfif.onrender.com"  # fallback if URL is None

print("Using BOT_TOKEN:", bot_token)
print("Using URL:", URL)

# Redis setup
redis_url = REDIS_URL or os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_conn = redis.from_url(redis_url)
queue = Queue(connection=redis_conn)

# Telegram bot with HTTPXRequest
request_config = HTTPXRequest(pool_timeout=10, read_timeout=15, write_timeout=15, connect_timeout=5)
bot = telegram.Bot(token=bot_token, request=request_config)

app = Flask(__name__)

# Async function to send message
async def send_message_async(token, chat_id, text):
    request_config = HTTPXRequest(pool_timeout=10, read_timeout=15, write_timeout=15, connect_timeout=5)
    bot = telegram.Bot(token=token, request=request_config)
    await bot.send_message(chat_id=chat_id, text=text)

# Sync wrapper for RQ queue
def enqueue_send_message(token, chat_id, text):
    asyncio.run(send_message_async(token, chat_id, text))

@app.route(f'/{bot_token}', methods=['POST'])
def respond():
    try:
        update_json = request.get_json(force=True)
        update = telegram.Update.de_json(update_json, bot)

        if not update.message:
            return 'ok', 200

        chat_id = update.message.chat.id
        text = update.message.text or ""

        if text == '/start':
            queue.enqueue(enqueue_send_message, bot_token, chat_id, "Welcome! How can I help you?")
        elif text == '/word':
            queue.enqueue(enqueue_send_message, bot_token, chat_id, "Please send me a word to define.")
        else:
            queue.enqueue(enqueue_send_message, bot_token, chat_id, f"You said: {text}")

        return 'ok', 200
    except Exception as e:
        print("Error in respond():", e)
        return 'ok', 200

# Synchronous webhook setup (run once manually)
def set_webhook():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(bot.set_webhook(f"{URL}/{bot_token}"))
    loop.close()
    return result

@app.route('/set_webhook', methods=['GET'])
def set_webhook_route():
    try:
        result = set_webhook()
        return f"Webhook set: {result}"
    except Exception as e:
        return f"Error setting webhook: {e}"

@app.route('/')
def index():
    return 'Bot is running!'

if __name__ == '__main__':
    app.run(threaded=True)
