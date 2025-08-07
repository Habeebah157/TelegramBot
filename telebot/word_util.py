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



load_dotenv()
nest_asyncio.apply()
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
API_KEY = os.getenv("WORDNIK_API_KEY")


bot_token = os.getenv("BOT_TOKEN")
if not bot_token:
    raise RuntimeError("BOT_TOKEN not set in environment variables")


request_config = HTTPXRequest(pool_timeout=10, read_timeout=15, write_timeout=15, connect_timeout=5)
bot = telegram.Bot(token=bot_token, request=request_config)
def escape_markdown(text: str) -> str:
    if not text:
        return ""
    escape_chars = escape_chars = r"_*[]~`>#+-=|{}.!|"
    return re.sub(rf"([{re.escape(escape_chars)}])", r"\\\1", text)

async def get_fun_fact_from_wikipedia(word):
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{word}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                extract = data.get("extract")
                description = data.get("description")
                page_url = data.get("content_urls", {}).get("desktop", {}).get("page")

                if extract:
                    first_sentence = extract.split(".")[0] + "."
                    fact_parts = ["🧠 <b>Fun Fact:</b>"]
                    if description:
                        fact_parts.append(f"<i>{description.capitalize()}</i>")
                    fact_parts.append(first_sentence)

                    if page_url:
                        fact_parts.append(f"<a href='{page_url}'>Read more</a>")

                    return "\n".join(fact_parts)
    return None

async def generate_with_gemini(prompt_text):
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")  # or "gemini-pro"
        response = await asyncio.to_thread(model.generate_content, prompt_text)

        # If candidates exist, extract the text
        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                first_part = candidate.content.parts[0]
                if hasattr(first_part, 'text'):
                    return first_part.text
        # Check for blocked prompt or quota exceeded
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            print(f"⚠️ Prompt blocked: {response.prompt_feedback.block_reason}")
        return []  # Fallback: empty list
    except Exception as e:
        print(f"❌ Gemini error: {e}")
        return []  # Fallback on any exception

FALLBACK_WORDS = [
    "serenity", "elated", "tenacity", "breeze", "wander", 
    "radiant", "puzzle", "imagine", "bold", "whisper"
]

async def get_common_random_word(min_corpus_count=50000):
    try:
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
                print(f"🔁 Wordnik Status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Wordnik word: {data}")
                    return data.get("word", "unknown")
                else:
                    print(f"❌ Wordnik failed: {await response.text()}")
    except Exception as e:
        print(f"❌ Wordnik exception: {e}")

    try:
        print("🔄 Trying fallback API (random-word-api.herokuapp.com)...")
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://random-word-api.herokuapp.com/word?number=1",
                timeout=5
            ) as response:
                print(f"🔁 Fallback API status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Fallback word: {data}")
                    return data[0]
                else:
                    print(f"❌ Fallback failed: {await response.text()}")
    except Exception as e:
        print(f"❌ Fallback API exception: {e}")

    return random.choice(FALLBACK_WORDS)
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

        return await generate_with_gemini(
            f"Provide the part of speech for the word '{word}' just in one word please."
        )
    except Exception as e:
        print(f"Error fetching part of speech: {e}")
        return "unknown"
    

async def get_image_from_wikipedia(word):
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{word}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                thumbnail = data.get("thumbnail", {})
                image_url = thumbnail.get("source")
                return image_url  # Might be None if not available
            else:
                print(f"Failed to get image from Wikipedia. Status: {response.status}")
    return None


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

