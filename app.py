import re
from flask import Flask, request
import telegram
import os

# Get bot token and app URL from environment variables
bot_token = os.environ.get('BOT_TOKEN')
URL = os.environ.get('URL')

TOKEN = bot_token
bot = telegram.Bot(token=TOKEN)
print("URL",URL)

app = Flask(__name__)

@app.route(f'/{TOKEN}', methods=['POST'])
def respond():
    print("Received POST request at webhook")
    update_json = request.get_json(force=True)
    print("Update JSON:", update_json)
    update = telegram.Update.de_json(update_json, bot)
    
    if not update.message:
        print("No message found in update")
        return 'ok'
    
    chat_id = update.message.chat.id
    msg_id = update.message.message_id
    text = update.message.text.encode('utf-8').decode() if update.message.text else ""
    print(f"Message text: {text}")
    
    # your existing logic ...


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
