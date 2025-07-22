import re
from flask import Flask, request
import telegram
import os
import asyncio
from telegram.request import HTTPXRequest
import threading
import redis
from rq import Queue

# TEMPORARY: Set Redis URL if not found in environment
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379')

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_conn = redis.from_url(redis_url)
queue = Queue(connection=redis_conn)

# Get bot token and app URL from environment variables
bot_token = os.environ.get('BOT_TOKEN')
URL = os.environ.get('URL')
print("Environment Variables:", URL)

# TEMPORARY: set URL if not found in environment
if URL is None:
    URL = "https://telegrambot-mfif.onrender.com"  # <-- add your bot URL here

# Configure custom HTTPXRequest to increase pool size and timeout
request_config = HTTPXRequest(pool_timeout=10, read_timeout=15, write_timeout=15, connect_timeout=5)
bot = telegram.Bot(token=bot_token, request=request_config)

print("BOT_TOKEN:", bot_token)
print("URL:", URL)

app = Flask(__name__)

# Create and start a dedicated event loop in a separate thread (not used now but kept if needed)
def start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

loop = asyncio.new_event_loop()
t = threading.Thread(target=start_loop, args=(loop,), daemon=True)
t.start()

# Async function that sends message to Telegram
async def send_message_async(token, chat_id, text):
    request_config = HTTPXRequest(pool_timeout=10, read_timeout=15, write_timeout=15, connect_timeout=5)
    bot = telegram.Bot(token=token, request=request_config)
    await bot.send_message(chat_id=chat_id, text=text)

# Sync wrapper to enqueue (will be called by RQ worker)
def enqueue_send_message(token, chat_id, text):
    import asyncio
    asyncio.run(send_message_async(token, chat_id, text))

@app.route(f'/{bot_token}', methods=['POST'])
def respond():
    try:
        update_json = request.get_json(force=True)
        print("Update JSON:", update_json)

        update = telegram.Update.de_json(update_json, bot)

        if not update.message:
            print("No message in update.")
            return 'ok', 200

        chat_id = update.message.chat.id
        text = update.message.text or ""
        print(f"Received message: {text} from chat_id: {chat_id}")

        # Enqueue message sending task instead of running directly
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

@app.route('/set_webhook', methods=['GET', 'POST'])
def set_webhook():
    s = bot.setWebhook(f"{URL}/{bot_token}")
    if s:
        return "webhook setup ok"
    else:
        return "webhook setup failed"

@app.route('/')
def index():
    return 'Bot is running!'

if __name__ == '__main__':
    app.run(threaded=True)
