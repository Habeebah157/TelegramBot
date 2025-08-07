import os
import urllib.parse
import asyncio
import google.generativeai as genai
from flask import Flask, request
import telegram
from telegram.request import HTTPXRequest
from urllib.parse import urljoin
import nest_asyncio
from dotenv import load_dotenv


load_dotenv()
nest_asyncio.apply()
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))



URL = os.getenv("URL")
if not URL:
    raise RuntimeError("URL not set in environment variables")

webhook_secret = os.getenv("WEBHOOK_SECRET", "supersecret")
API_KEY = os.getenv("WORDNIK_API_KEY")
bot_token = os.getenv("BOT_TOKEN")
request_config = HTTPXRequest(pool_timeout=10, read_timeout=15, write_timeout=15, connect_timeout=5)
bot = telegram.Bot(token=bot_token, request=request_config)

app = Flask(__name__)

from telebot.word_util import (
    escape_markdown,
    get_fun_fact_from_wikipedia, 
    get_common_random_word, 
    generate_with_gemini, 
    get_definition, 
    get_example_sentence, 
    get_pronunciation,
    get_synonyms,
    get_antonyms,
    get_audio_pronunciation,
    send_message_async, 
    send_voice_async,
    part_of_speech_async,
    get_image_from_wikipedia, 
    get_etymology
) 

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
            async def handle_word():
                words_list = await get_common_random_word()
                # random_word = random.choice(words_list)
                definition = await get_definition(words_list)
                pronunciation = get_pronunciation(words_list)
                example_sentence = await get_example_sentence(words_list)
                synonyms = await get_synonyms(words_list)
                antonyms = await get_antonyms(words_list)
                audio_url = asyncio.run(get_audio_pronunciation(words_list))                
                part_of_speech = await part_of_speech_async(words_list)
                # image_url = await get_random_cute_image_url()
                etymology = get_etymology(words_list)
                wikiinfo = await get_fun_fact_from_wikipedia(words_list)
                wiki_image = await get_image_from_wikipedia(words_list)

                

                prompt = f"Turn the list {words_list} into a short, clever mental model or schema that simplifies the concept. Make it witty and easy to understand. Make it short, not more than a 2 sentences. Use simple words please because this is for english learners"
                haiku = await generate_with_gemini(prompt)

                definition_text = "\n".join(definition)
                definition_text = escape_markdown(definition_text)

                example_sentence = escape_markdown(example_sentence) if example_sentence else None
                part_of_speech = escape_markdown(part_of_speech)
                etymology = escape_markdown(etymology)

                synonyms_escaped = [escape_markdown(s) for s in synonyms]
                antonyms_escaped = [escape_markdown(a) for a in antonyms]


                reply = f"<b>{words_list.capitalize()}</b>"
                if wiki_image:
                    reply += f"\n🖼️ <b>Wiki Image:</b> <a href='{wiki_image}'>View</a>"

                if pronunciation:
                    reply += f" <i>({escape_markdown(pronunciation)})</i>"
                definition_text = "\n".join(definition)
                reply += f":\n{definition_text}\n\n"

                


                if example_sentence:
                    reply += f"<i>Example:</i> {example_sentence}\n\n"
                reply += f"<b>Part of Speech:</b> {part_of_speech}\n"
                reply += f"<b>Synonyms:</b> {', '.join(synonyms_escaped) if synonyms else 'None'}\n"
                reply += f"<b>Antonyms:</b> {', '.join(antonyms_escaped) if antonyms else 'None'}\n"
                reply += f"\n<b>Etymology:</b> {etymology}\n"

                if haiku and haiku.strip():
                    haiku_escaped = escape_markdown(haiku)
                    reply += f"\n📝 <b>Word Association:</b>\n<pre>{haiku_escaped}</pre>\n"
                reply += f"\n<b>WikiInfo:</b> {wikiinfo}\n"
                reply += f"\n[🔊 Listen to pronunciation]({audio_url})"
                await bot.send_audio(chat_id=chat_id, audio=audio_url, caption="🔊 Listen to pronunciation")

                asyncio.run(send_message_async(chat_id, reply))
                # asyncio.run(send_voice_async(chat_id, audio_url))

            asyncio.run(handle_word())
        elif text == '/quiz': 
            asyncio.run(send_message_async(chat_id, "Ok, welcome to the quiz. I am excited to do this for you. "))

        else:
            async def handle_other():
                escaped_text = escape_markdown(text)
                await send_message_async(chat_id, f"You said: {escaped_text}")

            asyncio.run(handle_other())

        return 'ok', 200

    except Exception as e:
        print("❌ Error in respond():", e)
        return 'ok', 200

@app.route('/set_webhook', methods=['GET'])
def set_webhook_route():
    try:
        webhook_url = urljoin(URL.rstrip('/') + '/', webhook_secret)
        result = asyncio.run(bot.set_webhook(webhook_url))
        return f"Webhook set: {result}"
    except Exception as e:
        return f"Error setting webhook: {e}"

@app.route('/')
def index():
    return 'Bot is running!'

if __name__ == '__main__':
    app.run(threaded=True)
