import json

INPUT_FILE = "all_pokemon_with_tiers.json"
OUTPUT_FILE = "all_pokemon_with_strategies.json"

def add_empty_strategies(data):
    updated_count = 0
    for entry in data:
        if "strategies" not in entry:  # Only add if missing, to avoid overwriting
            entry["strategies"] = [
                {
                    "name": "",
                    "moveslots": ["", "", "", ""],
                    "item": "",
                    "ability": "",
                    "nature": "",
                    "evs": "",
                    "tera_type": ""
                }
            ]
            updated_count += 1
    print(f"{updated_count} Pokémon updated with empty strategy template.")
    return data

def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    enriched_data = add_empty_strategies(data)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(enriched_data, f, indent=2)

    print(f"\nData with placeholders written to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
