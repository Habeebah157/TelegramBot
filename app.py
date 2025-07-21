import re
from flask import Flask, request
import telegram
import os
import asyncio
# Get bot token and app URL from environment variables
bot_token = os.environ.get('BOT_TOKEN')
URL = os.environ.get('URL')

TOKEN = bot_token
bot = telegram.Bot(token=TOKEN)
print("URL", URL)

app = Flask(__name__)

@app.route(f'/{TOKEN}', methods=['POST'])
def respond():
    update_json = request.get_json(force=True)
    update = telegram.Update.de_json(update_json, bot)

    if not update.message:
        return 'ok', 200

    chat_id = update.message.chat.id
    text = update.message.text or ""

    if text == '/start':
        asyncio.run(bot.send_message(chat_id=chat_id, text="Welcome! How can I help you?"))
    else:
        asyncio.run(bot.send_message(chat_id=chat_id, text=f"You said: {text}"))

    return 'ok', 200

@app.route('/set_webhook', methods=['GET', 'POST'])
def set_webhook():
    s = bot.setWebhook(f"{URL}/{TOKEN}")
    if s:
        return "webhook setup ok"
    else:
        return "webhook setup failed"

@app.route('/')
def index():
    return 'Bot is running!'

if __name__ == '__main__':
    app.run(threaded=True)
