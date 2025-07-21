import re
from flask import Flask, request
import telegram
import os
import asyncio
from telegram.request import HTTPXRequest

# Get bot token and app URL from environment variables
bot_token = os.environ.get('BOT_TOKEN')
URL = os.environ.get('URL')

# Configure custom HTTPXRequest to increase pool size and timeout
request_config = HTTPXRequest(pool_timeout=10, read_timeout=15, write_timeout=15, connect_timeout=5, max_connections=50)
bot = telegram.Bot(token=bot_token, request=request_config)

print("BOT_TOKEN:", bot_token)
print("URL:", URL)
app = Flask(__name__)

loop = asyncio.get_event_loop()

@app.route(f'/{bot_token}', methods=['POST'])
def respond():
    update_json = request.get_json(force=True)
    update = telegram.Update.de_json(update_json, bot)

    if not update.message:
        return 'ok', 200

    chat_id = update.message.chat.id
    text = update.message.text or ""

    async def handle_message():
        if text == '/start':
            await bot.send_message(chat_id=chat_id, text="Welcome! How can I help you?")
        elif text == '/word':
            await bot.send_message(chat_id=chat_id, text="Please send me a word to define.")
        else:
            await bot.send_message(chat_id=chat_id, text=f"You said: {text}")

    asyncio.run_coroutine_threadsafe(handle_message(), loop)
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
