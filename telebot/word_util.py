import asyncio
import google.generativeai as genai
import re
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])  # Make sure to add this to your .env file


import random

async def generate_with_gemini(prompt_text):
    try:
        # Use a more standard model name - adjust based on what's available to you
        model = genai.GenerativeModel("gemini-1.5-flash")  # or "gemini-pro"
        
        response = await asyncio.to_thread(model.generate_content, prompt_text)

        # --- DEBUGGING OUTPUT ---
        print("\n--- Gemini Response Debug ---")
        print(f"Prompt sent: '{prompt_text}'")
        print(f"Response object type: {type(response)}")
        # --- END DEBUGGING OUTPUT ---

        if response.candidates:
            print("these are the candidates", response.candidates)
            candidate = response.candidates[0]
            # --- DEBUGGING OUTPUT ---
            print(f"Candidate finish reason: {candidate.finish_reason}")
            print(f"Candidate content object (full dump): {candidate.content}")
            # --- END DEBUGGING OUTPUT ---

            if candidate.content and candidate.content.parts and hasattr(candidate.content.parts[0], 'text'):
                generated_text = candidate.content.parts[0].text
                print(f"Successfully extracted text content (first 100 chars): '{generated_text[:100]}...'")
                return generated_text
            else:
                print("Error: Candidate content structure is not as expected (missing parts or text in first part).")
                return "No text content could be extracted from the model's response."
        else:
            print("No candidates returned in the response.")
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                print(f"Prompt blocked due to: {response.prompt_feedback.block_reason}")
                print(f"Safety ratings: {response.prompt_feedback.safety_ratings}")
            return "No content could be generated for this prompt (blocked or empty response)."

    except Exception as e:
        print(f"An error occurred during content generation: {e}")
        return f"An error occurred: {e}"

async def escape_markdown(text: str) -> str:
    if not text:
        return ""
    # MarkdownV2 special characters to escape
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(rf"([{re.escape(escape_chars)}])", r"\\\1", text)

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


