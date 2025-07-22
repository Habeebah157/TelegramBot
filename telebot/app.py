import os
import asyncio
from flask import Flask, request
import telegram
from telegram.request import HTTPXRequest
import redis
from rq import Queue
from urllib.parse import urljoin

# Load environment variables
bot_token = os.environ["BOT_TOKEN"]
URL = os.environ["URL"]  # e.g., "https://yourdomain.com"
redis_url = os.environ["REDIS_URL"]
webhook_secret = os.environ.get("WEBHOOK_SECRET", "supersecret")  # Optional secret path

# Set up Redis queue
redis_conn = redis.from_url(redis_url)
queue = Queue(connection=redis_conn)

# Configure Telegram Bot with HTTPX
request_config = HTTPXRequest(pool_timeout=10, read_timeout=15, write_timeout=15, connect_timeout=5)
bot = telegram.Bot(token=bot_token, request=request_config)

# Flask app
app = Flask(__name__)

# Async function to send messages
async def send_message_async(token, chat_id, text):
    request_config = HTTPXRequest(pool_timeout=10, read_timeout=15, write_timeout=15, connect_timeout=5)
    bot = telegram.Bot(token=token, request=request_config)
    await bot.send_message(chat_id=chat_id, text=text)

# Sync wrapper for RQ
def enqueue_send_message(token, chat_id, text):
    asyncio.run(send_message_async(token, chat_id, text))

# Webhook route — uses secret path instead of bot token for better security
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
            queue.enqueue(enqueue_send_message, bot_token, chat_id, "Welcome! How can I help you?")
        elif text == '/word':
            queue.enqueue(enqueue_send_message, bot_token, chat_id, "Please send me a word to define.")
        else:
            queue.enqueue(enqueue_send_message, bot_token, chat_id, f"You said: {text}")

        return 'ok', 200
    except Exception as e:
        print("Error in respond():", e)
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
