import os
import asyncio
from flask import Flask, request
import telegram
from telegram.request import HTTPXRequest
from urllib.parse import urljoin

# Load environment variables
bot_token = os.environ["BOT_TOKEN"]
URL = os.environ["URL"]
webhook_secret = os.environ.get("WEBHOOK_SECRET", "supersecret")

print("Loaded BOT_TOKEN:", bot_token)

# Configure Telegram Bot with HTTPX
request_config = HTTPXRequest(pool_timeout=10, read_timeout=15, write_timeout=15, connect_timeout=5)
bot = telegram.Bot(token=bot_token, request=request_config)

# Flask app
app = Flask(__name__)

# Async function to send messages
async def send_message_async(chat_id, text):
    try:
        print(f"[Async ✅] Sending to {chat_id}: {text}")
        await bot.send_message(chat_id=chat_id, text=text)
    except Exception as e:
        print(f"[Async ❌] Failed to send to {chat_id}: {e}")

# Webhook handler
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

        # Prepare response text
        if text == '/start':
            response_text = "Welcome! How can I help you?"
        elif text == '/word':
            response_text = "Please send me a word to define."
        else:
            response_text = f"You said: {text}"

        # Run send message asynchronously
        asyncio.create_task(send_message_async(chat_id, response_text))

        return 'ok', 200
    except Exception as e:
        print("❌ Error in respond():", e)
        return 'ok', 200

# Route to set webhook manually
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

# Run the Flask app
if __name__ == '__main__':
    app.run(threaded=True)
