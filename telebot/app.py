import os
import random
import string
import urllib.parse
import re
import requests
import asyncio
import google.generativeai as genai
from flask import Flask, request
import telegram
from telegram.request import HTTPXRequest
from urllib.parse import urljoin
import nest_asyncio
from dotenv import load_dotenv
import aiohttp

# Load environment variables once at the top
load_dotenv()

# Apply nest_asyncio to allow nested event loops inside Flask
nest_asyncio.apply()

# Configure Gemini API with your key from .env
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# Grab environment variables, with basic checks
bot_token = os.getenv("BOT_TOKEN")
if not bot_token:
    raise RuntimeError("BOT_TOKEN not set in environment variables")

URL = os.getenv("URL")
if not URL:
    raise RuntimeError("URL not set in environment variables")

webhook_secret = os.getenv("WEBHOOK_SECRET", "supersecret")

# Telegram bot setup with HTTPXRequest config
request_config = HTTPXRequest(pool_timeout=10, read_timeout=15, write_timeout=15, connect_timeout=5)
bot = telegram.Bot(token=bot_token, request=request_config)

app = Flask(__name__)

def escape_markdown(text: str) -> str:
    if not text:
        return ""
    escape_chars = r"_*[]()~`>#+-=|{}.!|"
    return re.sub(rf"([{re.escape(escape_chars)}])", r"\\\1", text)

async def generate_with_gemini(prompt_text):
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")  # or "gemini-pro"
        response = await asyncio.to_thread(model.generate_content, prompt_text)

        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts and hasattr(candidate.content.parts[0], 'text'):
                return candidate.content.parts[0].text
            else:
                return "No text content could be extracted from the model's response."
        else:
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                print(f"Prompt blocked: {response.prompt_feedback.block_reason}")
            return "No content could be generated for this prompt."
    except Exception as e:
        print(f"Error during content generation: {e}")
        return f"Error: {e}"

def get_low_freq_random_words(n=10, freq_threshold=500):
    words = []
    try:
        for _ in range(n):
            letter = random.choice(string.ascii_lowercase)
            response = requests.get(f'https://api.datamuse.com/words?sp={letter}*&md=f&max=1000', timeout=5)
            data = response.json()
            filtered = [
                w['word'] for w in data
                if 'tags' in w
                for tag in w['tags']
                if tag.startswith('f:') and float(tag[2:]) < freq_threshold
            ]
            if filtered:
                words.append(random.choice(filtered))
            else:
                words.append(random.choice(["arcane", "obscure", "esoteric", "rare", "uncommon"]))
        return words
    except Exception as e:
        print(f"Error fetching low frequency words: {e}")
        return ["arcane", "obscure", "esoteric"]

async def get_definition(word):
    try:
        def fetch_definition():
            url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
            response = requests.get(url, timeout=5)
            return response.json()

        data = await asyncio.to_thread(fetch_definition)

        all_definitions = []

        if isinstance(data, list) and data:
            for meaning in data[0].get("meanings", []):
                part_of_speech = meaning.get("partOfSpeech", "")
                for definition in meaning.get("definitions", []):
                    def_text = definition.get("definition", "No definition found.")
                    full_def = f"{part_of_speech}: {def_text}" if part_of_speech else def_text
                    all_definitions.append(full_def)

        if all_definitions:
            return all_definitions
        else:
            # Fallback to AI generation
            prompt = f"Write a simple definition for the word '{word}'."
            generated_text = await generate_with_gemini(prompt)
            return [generated_text]

    except Exception as e:
        print(f"Error fetching definition: {e}")
        return ["Error fetching definition."]

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
        return generate_with_gemini(f"Provide an example sentence for the word '{word}'.")
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

async def get_audio_pronunciation(word, lang='en'):
    base_url = "https://translate.google.com/translate_tts"
    params = {
        "ie": "UTF-8",
        "q": word,
        "tl": lang,
        "client": "tw-ob"
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"

async def send_message_async(chat_id, text):
    try:
        await bot.send_message(chat_id=chat_id, text=text.encode('utf-16', 'surrogatepass').decode('utf-16'), parse_mode='HTML')

    except Exception as e:
        print(f"[❌] Failed to send message: {e}")

async def send_voice_async(chat_id, voice_url):
    try:
        await bot.send_voice(chat_id=chat_id, voice=voice_url)
    except Exception as e:
        print(f"[❌] Failed to send voice: {e}")

async def part_of_speech_async(word):
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                data = await response.json()

                if isinstance(data, list) and len(data) > 0:
                    meanings = data[0].get("meanings", [])

                    if meanings:
                        part = meanings[0].get("partOfSpeech", "unknown")
                        return part

        return await generate_with_gemini(f"Provide the part of speech for the word  '{word}' just in one word please.")
    except Exception as e:
        print(f"Error fetching part of speech: {e}")
        return "unknown"

async def get_random_cute_image_url():
    try:
        access_key = os.environ.get("UNSPLASH_ACCESS_KEY")
        query = "cute pastel illustration silly"
        url = f"https://api.unsplash.com/photos/random?query={urllib.parse.quote(query)}&client_id={access_key}"
        response = requests.get(url, timeout=5)
        data = response.json()
        return data['urls']['regular']
    except Exception as e:
        print(f"Error fetching image: {e}")
        return None

def get_etymology(word):
    try:
        api_key = os.environ["WORDNIK_API_KEY"]
        url = f"https://api.wordnik.com/v4/word.json/{word}/etymologies?useCanonical=true&limit=1&api_key={api_key}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if isinstance(data, list) and data:
            return data[0]
        return "No etymology found."
    except Exception as e:
        print(f"Error fetching etymology: {e}")
        return "Error fetching etymology."

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
                words_list = get_low_freq_random_words()
                random_word = random.choice(words_list)
                definition = await get_definition(random_word)
                pronunciation = get_pronunciation(random_word)
                example_sentence = get_example_sentence(random_word)
                synonyms = get_synonyms(random_word)
                antonyms = get_antonyms(random_word)
                audio_url = await get_audio_pronunciation(random_word)
                part_of_speech = await part_of_speech_async(random_word)
                image_url = await get_random_cute_image_url()
                etymology = get_etymology(random_word)

                prompt = f"Write a funny visual Haiku about the word '{random_word}'. Keep it short and witty."
                haiku = await generate_with_gemini(prompt)

                definition_text = "\n".join(definition)
                definition_text = escape_markdown(definition_text)

                example_sentence = escape_markdown(example_sentence) if example_sentence else None
                part_of_speech = escape_markdown(part_of_speech)
                etymology = escape_markdown(etymology)

                synonyms_escaped = [escape_markdown(s) for s in synonyms]
                antonyms_escaped = [escape_markdown(a) for a in antonyms]

                reply = f"<b>{random_word.capitalize()}</b>"
                if pronunciation:
                    reply += f" <i>({escape_markdown(pronunciation)})</i>"
                definition_text = "\n".join(definition)
                reply += f":\n{definition_text}\n\n"


                if example_sentence:
                    reply += f"<i>Example:</i> {example_sentence}\n\n"
                reply += f"<b>Part of Speech:</b> {part_of_speech}\n"
                reply += f"<b>Synonyms:</b> {', '.join(synonyms_escaped) if synonyms else 'None'}\n"
                reply += f"<b>Antonyms:</b> {', '.join(antonyms_escaped) if antonyms else 'None'}\n"
                reply += f"\n🔊 <a href='{audio_url}'>Listen to pronunciation</a>"
                reply += f"\n<b>Etymology:</b> {etymology}\n"

                if haiku and haiku.strip():
                    haiku_escaped = escape_markdown(haiku)
                    reply += f"\n📝 <b>Haiku:</b>\n<pre>{haiku_escaped}</pre>\n"

                if image_url:
                    reply += f"\n\n🖼️ <b>Visual Vibe:</b> <a href='{image_url}'>View image</a>"

                await send_message_async(chat_id, reply)
                await send_voice_async(chat_id, audio_url)

            asyncio.run(handle_word())

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
