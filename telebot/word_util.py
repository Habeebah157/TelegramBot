import requests
import random

def get_medium_adjectives():
    try:
        response = requests.get('https://api.datamuse.com/words?sp=*&md=pf&max=1000', timeout=5)
        words = response.json()
        print("Fetched words from API:", len(words))

        def get_freq(word_obj):
            if 'tags' in word_obj:
                for tag in word_obj['tags']:
                    if tag.startswith('f:'):
                        try:
                            return float(tag[2:])
                        except ValueError:
                            return 0
            return 0

        def is_adjective(word_obj):
            return 'tags' in word_obj and 'adj' in word_obj['tags']

        medium_adjectives = [
            w['word'] for w in words
            if is_adjective(w) and 700 < get_freq(w) < 10000
        ]

        if not medium_adjectives:
            return default_adjectives()

        return medium_adjectives
    except Exception as e:
        print(f"Error fetching adjectives: {e}")
        return default_adjectives()

def default_adjectives():
    return [
        "intermediate", "moderate", "subtle", "robust", "complex",
        "steady", "dynamic", "vivid", "precise", "refined"
    ]

def get_definition(word):
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if isinstance(data, list) and data:
            meanings = data[0].get("meanings", [])
            if meanings:
                definitions = meanings[0].get("definitions", [])
                if definitions:
                    return definitions[0].get("definition", "No definition found.")
        return "Sorry, no definition found."
    except Exception as e:
        print(f"Error fetching definition: {e}")
        return "Error fetching definition."

def get_example_sentence(word):
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if isinstance(data, list) and data:
            meanings = data[0].get("meanings", [])
            for meaning in meanings:
                definitions = meaning.get("definitions", [])
                for definition in definitions:
                    example = definition.get("example")
                    if example:
                        return example
        return None
    except Exception as e:
        print(f"Error fetching example sentence: {e}")
        return None

def get_pronunciation(word):
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if isinstance(data, list) and data:
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
