import json

# Load Pokémon data
with open("all_pokemon_tiered.json", "r", encoding="utf-8") as f:
    pokemon_data = json.load(f)

# Helper to load tier list from text file
def load_tier_list(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return set(line.strip().lower() for line in f if line.strip())

# Load tier lists
uber_pokemon = load_tier_list("uber.txt")
ou_pokemon = load_tier_list("ou.txt")
uu_pokemon = load_tier_list("uu.txt")

# Update tier and log ranked Pokémon
for pokemon in pokemon_data:
    name = pokemon["name"].lower()
    if name in uber_pokemon:
        tier = "Uber"
    elif name in ou_pokemon:
        tier = "OU"
    elif name in uu_pokemon:
        tier = "UU"
    else:
        tier = "Unranked"

    pokemon["Tier"] = tier
    if tier != "Unranked":
        print(f"{pokemon['name'].capitalize()} - Tier set to: {tier}")

# Save updated JSON
with open("all_pokemon_tiered_with_tiers.json", "w", encoding="utf-8") as f:
    json.dump(pokemon_data, f, indent=2)

print("\nRanked tiers have been assigned and saved to 'all_pokemon_tiered_with_tiers.json'.")
