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
print(API_KEY)
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