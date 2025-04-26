import os
import json
import requests
from time import sleep

BASE_URL = "https://pokeapi.co/api/v2"
POKEMON_ENDPOINT = f"{BASE_URL}/pokemon?limit=10000"
SAVE_DIR = "pokemon_data"

os.makedirs(SAVE_DIR, exist_ok=True)

def get_all_pokemon_urls():
    response = requests.get(POKEMON_ENDPOINT)
    response.raise_for_status()
    return [pokemon['url'] for pokemon in response.json()['results']]

def get_pokemon_data(url):
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    return {
        "id": data['id'],
        "name": data['name'],
        "abilities": [ab['ability']['name'] for ab in data['abilities']],
        "stats": {stat['stat']['name']: stat['base_stat'] for stat in data['stats']},
        "types": [t['type']['name'] for t in data['types']],
        "sprite_url": data['sprites']['front_default']
    }

def save_pokemon_data(pokemon):
    filename = os.path.join(SAVE_DIR, f"{pokemon['name']}.json")
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(pokemon, f, indent=2)

def main():
    print("Fetching list of Pokémon...")
    urls = get_all_pokemon_urls()

    for i, url in enumerate(urls):
        try:
            pokemon = get_pokemon_data(url)
            save_pokemon_data(pokemon)
            print(f"Saved: {pokemon['name']} ({i + 1}/{len(urls)})")
            sleep(0.2)  # prevent API rate limiting
        except Exception as e:
            print(f"Failed to process {url}: {e}")

if __name__ == "__main__":
    main()