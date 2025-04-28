import os
import json
import requests
from time import sleep

BASE_URL = "https://pokeapi.co/api/v2"
POKEMON_ENDPOINT = f"{BASE_URL}/pokemon?limit=10000"
OUTPUT_FILE = "all_pokemon.json"

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

def main():
    print("Fetching list of Pokémon...")
    urls = get_all_pokemon_urls()

    all_pokemon = []

    for i, url in enumerate(urls):
        try:
            pokemon = get_pokemon_data(url)
            all_pokemon.append(pokemon)
            print(f"Fetched: {pokemon['name']} ({i + 1}/{len(urls)})")
            sleep(0.2)  # avoid hitting API rate limits
        except Exception as e:
            print(f"Error fetching {url}: {e}")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_pokemon, f, indent=2)
    print(f"Saved all data to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
