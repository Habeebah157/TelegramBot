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
API_KEY = os.getenv("WORDNIK_API_KEY")
print(API_KEY)

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
                return []
        else:
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                print(f"Prompt blocked: {response.prompt_feedback.block_reason}")
            return []
    except Exception as e:
        print(f"Error during content generation: {e}")
        return []

async def get_common_random_word(min_corpus_count=50000):
    try:
        print("HELLO HERE")
        async with aiohttp.ClientSession() as session:
            params = {
                "hasDictionaryDef": "true",
                "minCorpusCount": min_corpus_count,
                "api_key": API_KEY
            }
            async with session.get(
                "https://api.wordnik.com/v4/words.json/randomWord",
                params=params,
                timeout=5
            ) as response:
                print(f"Status code: {response.status}")
                if response.status != 200:
                    text = await response.text()
                    print(f"Failed request: {text}")
                    return "error"
                data = await response.json()
                print(f"Response JSON: {data}")
                return data.get("word", "unknown")
    except Exception as e:
        print(f"Error fetching word: {e}")
        return "error"
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

async def get_example_sentence(word):
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
        return await generate_with_gemini(f"Provide an example sentence for the word '{word}'.")
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

async def get_synonyms(word, max_results=5):
    try:
        response = requests.get(f'https://api.datamuse.com/words?rel_syn={word}&max={max_results}', timeout=5)
        synonyms = response.json()
        res = [w['word'] for w in synonyms] if synonyms else []

        if res:
            return res
        else:
            prompt = f"List a few concise synonyms of the word '{word}', separated by commas. Just the words, no explanations. if none, return []"
            gemini_response = await generate_with_gemini(prompt)
            print(f"Gemini response: {gemini_response}")
            words = [w.strip() for w in gemini_response.split(",") if w.strip()]
            return words
    except Exception as e:
        print(f"Error fetching synonyms: {e}")
        return []

async def get_antonyms(word, max_results=5):
    try:
        response = requests.get(f'https://api.datamuse.com/words?rel_ant={word}&max={max_results}', timeout=5)
        antonyms = response.json()
        res = [w['word'] for w in antonyms] if antonyms else []

        if res:
            print(res)
            return res
        else:
            prompt = f"List a few concise antonyms of the word '{word}', separated by commas. Just the words, no explanations. if none, return []"
            gemini_response = await generate_with_gemini(prompt)
            print(f"Gemini response: {gemini_response}")
            words = [w.strip() for w in gemini_response.split(",") if w.strip()]
            return words

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
    url = f"https://api.wordnik.com/v4/word.json/{word}/definitions"
    params = {
        "limit": 1,
        "includeRelated": "false",
        "useCanonical": "true",
        "api_key": API_KEY
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=5) as response:
                if response.status != 200:
                    text = await response.text()
                    print(f"Failed Wordnik part of speech fetch: {response.status} {text}")
                    # fallback to Gemini
                    return await generate_with_gemini(
                        f"Provide the part of speech for the word '{word}' just in one word please."
                    )

                data = await response.json()

                if isinstance(data, list) and len(data) > 0:
                    pos = data[0].get("partOfSpeech")
                    if pos:
                        return pos

        # fallback to Gemini if no data found
        return await generate_with_gemini(
            f"Provide the part of speech for the word '{word}' just in one word please."
        )
    except Exception as e:
        print(f"Error fetching part of speech: {e}")
        return "unknown"
# async def get_random_cute_image_url():
#     try:
#         access_key = os.environ.get("UNSPLASH_ACCESS_KEY")
#         query = "cute pastel illustration silly"
#         url = f"https://api.unsplash.com/photos/random?query={urllib.parse.quote(query)}&client_id={access_key}"
#         response = requests.get(url, timeout=5)
#         data = response.json()
#         return data['urls']['regular']
#     except Exception as e:
#         print(f"Error fetching image: {e}")
#         return None

def get_etymology(word):
    try:
        url = f"https://api.wordnik.com/v4/word.json/{word}/etymologies?useCanonical=true&limit=1&api_key={API_KEY}"
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
                words_list = await get_common_random_word()
                # random_word = random.choice(words_list)
                definition = await get_definition(words_list)
                pronunciation = get_pronunciation(words_list)
                example_sentence = await get_example_sentence(words_list)
                synonyms = await get_synonyms(words_list)
                antonyms = await get_antonyms(words_list)
                audio_url = await get_audio_pronunciation(words_list)
                part_of_speech = await part_of_speech_async(words_list)
                # image_url = await get_random_cute_image_url()
                etymology = get_etymology(words_list)

                prompt = f"Write a funny visual Haiku about the word '{words_list}'. Keep it short and witty."
                haiku = await generate_with_gemini(prompt)

                definition_text = "\n".join(definition)
                definition_text = escape_markdown(definition_text)

                example_sentence = escape_markdown(example_sentence) if example_sentence else None
                part_of_speech = escape_markdown(part_of_speech)
                etymology = escape_markdown(etymology)

                synonyms_escaped = [escape_markdown(s) for s in synonyms]
                antonyms_escaped = [escape_markdown(a) for a in antonyms]

                reply = f"<b>{words_list.capitalize()}</b>"
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

                # if image_url:
                #     reply += f"\n\n🖼️ <b>Visual Vibe:</b> <a href='{image_url}'>View image</a>"

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
