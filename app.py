from flask import Flask, render_template, request, session, redirect, url_for, jsonify
import json
import random
from difflib import get_close_matches
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'

with open("all_pokemon_with_tiers.json", "r", encoding="utf-8") as f:
    all_pokemon = json.load(f)

TIER_OPTIONS = sorted(set(p["Tier"] for p in all_pokemon if p["Tier"] != "Unranked"))

def get_type_icons(types):
    return [(t, url_for("static", filename=f"type-icons/{t.lower()}.png")) for t in types]

def get_hints(pokemon, hint_index):
    type_icons = get_type_icons(pokemon["types"])
    static_hints = [
        {"label": "Types", "types": type_icons},
        {"label": "Tier", "text": pokemon["Tier"]}
    ]
    dynamic_hints = [
        {"label": "Abilities", "text": ', '.join(pokemon['abilities'])}
    ]

    # Tier background colors for strategy cards
    tier_classes = {
        "Ubers": "bg-red-600",
        "OU": "bg-blue-600",
        "UU": "bg-purple-600",
        "RU": "bg-green-600",
        "NU": "bg-yellow-600",
        "PU": "bg-pink-600"
    }
    tier_class = tier_classes.get(pokemon["Tier"], "bg-gray-600")

    # Stats with colored horizontal bars
    desired_order = ["HP", "Attack", "Defense", "Special Attack", "Special Defense", "Speed"]
    stat_rows = []
    for stat in desired_order:
        value = pokemon["stats"].get(stat, 0)
        width = min(100, int(value / 180 * 100))  # scale bar width
        if value < 60:
            color = "bg-red-500"
        elif value < 90:
            color = "bg-orange-400"
        elif value < 120:
            color = "bg-yellow-300"
        else:
            color = "bg-lime-400"

        row = f'''
        <div class="flex items-center gap-2 mb-1">
            <span class="w-24 text-right font-medium">{stat}:</span>
            <span class="w-10 text-left">{value}</span>
            <div class="flex-1 h-3 rounded {color}" style="max-width: {width}%;"></div>
        </div>
        '''
        stat_rows.append(row)

    stats_html = "".join(stat_rows)
    dynamic_hints.append({"label": "Stats", "html": stats_html, "tier_class": "bg-gray-700"})

    # Strategy hints
    if "strategies" in pokemon and pokemon["strategies"]:
        for s in pokemon["strategies"]:
            lines = []
            if s.get("name"): lines.append(f"<strong>Strategy:</strong> {s['name']}")
            if s.get("ability"): lines.append(f"<strong>Ability:</strong> {s['ability']}")
            if s.get("moveslots"):
                moves_list = "".join(f"<li>{move}</li>" for move in s["moveslots"])
                lines.append(f"<strong>Moves:</strong><ul style='list-style: disc inside;'>{moves_list}</ul>")
            if s.get("item"): lines.append(f"<strong>Item:</strong> {s['item']}")
            if s.get("nature"): lines.append(f"<strong>Nature:</strong> {s['nature']}")
            if s.get("evs"): lines.append(f"<strong>EVs:</strong> {s['evs']}")
            if s.get("tera_type"): lines.append(f"<strong>Tera Type:</strong> {s['tera_type']}")
            full_html = "<br>".join(lines)
            dynamic_hints.append({"label": "Strategy", "html": full_html, "tier_class": tier_class})
    else:
        dynamic_hints.append({
            "label": "Strategy",
            "html": "<em>This Pokémon has no applicable Smogon strategies.</em>",
            "tier_class": "bg-gray-600"
        })

    dynamic_hints.append({"label": "ID", "text": pokemon["id"]})

    return static_hints + dynamic_hints[:hint_index]

@app.route("/")
def index():
    return redirect(url_for("game"))

@app.route("/game", methods=["GET", "POST"])
def game():
    if request.method == "POST":
        session["tiers"] = request.form.getlist("tiers")
        pick_new_pokemon()
        return redirect(url_for("game"))

    if "pokemon" not in session:
        pick_new_pokemon()

    pokemon = session["pokemon"]
    hints = get_hints(pokemon, session.get("hint_index", 0))

    return render_template(
        "game.html",
        hints=hints,
        score=session.get("score", 0),
        rounds=session.get("rounds", 0),
        image_revealed=session.get("revealed", False),
        image_url=pokemon["sprite_url"],
        tiers=TIER_OPTIONS,
        selected_tiers=session.get("tiers", []),
        hint_index=session.get("hint_index", 0)
    )

@app.route("/guess", methods=["POST"])
def guess():
    user_guess = request.form["guess"].strip().lower()
    pokemon = session["pokemon"]
    correct = user_guess == pokemon["name"].lower()

    if correct and not session.get("revealed", False):
        session["revealed"] = True
        session["score"] = session.get("score", 0) + max(6 - session.get("hint_index", 0), 1)
        session["rounds"] = session.get("rounds", 0) + 1
    elif not correct:
        session["hint_index"] = session.get("hint_index", 0) + 1

    return redirect(url_for("game"))

@app.route("/next")
def next_pokemon():
    pick_new_pokemon()
    return redirect(url_for("game"))

@app.route("/reset")
def reset_game():
    session.clear()
    return redirect(url_for("game"))

@app.route("/autocomplete")
def autocomplete():
    query = request.args.get("q", "").lower()
    names = [p["name"] for p in all_pokemon]
    matches = get_close_matches(query, names, n=10, cutoff=0.3)
    return jsonify(matches)

def pick_new_pokemon():
    tiers = session.get("tiers", [])
    if not tiers:
        tiers = ["OU"]
        session["tiers"] = tiers
    filtered = [p for p in all_pokemon if p["Tier"] in tiers]
    session["pokemon"] = random.choice(filtered)
    session["hint_index"] = 0
    session["revealed"] = False

@app.route("/giveup")
def giveup():
    session["revealed"] = True
    session["rounds"] = session.get("rounds", 0) + 1
    return redirect(url_for("game"))

if __name__ == "__main__":
    app.run(debug=True)
