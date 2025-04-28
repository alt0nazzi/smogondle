from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from datetime import datetime
import json
import random
from difflib import get_close_matches
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'

with open("all_pokemon_with_tiers.json", "r", encoding="utf-8") as f:
    all_pokemon = json.load(f)

TIER_OPTIONS = sorted(set(p["Tier"] for p in all_pokemon if p["Tier"] != "Unranked"))

DAILY_LEADERBOARD_FILE = "daily_leaderboard.json"

if os.path.exists(DAILY_LEADERBOARD_FILE):
    with open(DAILY_LEADERBOARD_FILE, "r") as f:
        daily_leaderboard = json.load(f)
else:
    daily_leaderboard = {}

def save_daily_score(player_name, score, time_taken):
    today = datetime.now().strftime("%Y-%m-%d")
    
    if os.path.exists(DAILY_LEADERBOARD_FILE):
        with open(DAILY_LEADERBOARD_FILE, "r") as f:
            fresh_data = json.load(f)
    else:
        fresh_data = {}

    if today not in fresh_data:
        fresh_data[today] = []

    fresh_data[today].append((player_name, score, time_taken))
    fresh_data[today] = sorted(
        fresh_data[today],
        key=lambda x: (-x[1], x[2])
    )[:10]

    with open(DAILY_LEADERBOARD_FILE, "w") as f:
        json.dump(fresh_data, f)

    global daily_leaderboard
    daily_leaderboard = fresh_data

def calculate_points():
    hint_index = session.get("hint_index", 0)
    revealed_hints = hint_index

    if revealed_hints == 0:
        base_points = 100
    elif revealed_hints == 1:
        base_points = 80
    elif revealed_hints == 2:
        base_points = 60
    elif revealed_hints == 3:
        base_points = 40
    elif revealed_hints == 4:
        base_points = 20
    else:
        base_points = 10

    if revealed_hints < 4:
        multiplier = 1.5
    else:
        multiplier = 1

    return int(base_points * multiplier)

def get_type_icons(types):
    return [{"name": t, "url": f"/static/type-icons/{t.lower()}.png"} for t in types]

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
        "Uber": "bg-red-600",
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

@app.route("/game")
def game():
    if "pokemon" not in session:
        pick_new_pokemon()
        if "start_time" not in session:
            session["start_time"] = datetime.now().timestamp()
    pokemon = session["pokemon"]

    score = session.get("score", 0)
    rounds = session.get("rounds", 0)
    show_leaderboard = session.pop('show_leaderboard', False)
    revealed = session.get("revealed", False)
    selected_tiers = session.get("tiers", [])
    hint_index = session.get("hint_index", 0)
    last_correct = session.get("last_correct", False)
    guess_wrong = session.pop("guess_wrong", False)
    bonus_multiplier = session.pop("bonus_multiplier", False)
    points_earned = session.pop("points_earned", 0)
    intro_animation = False

    if "intro_seen" not in session:
        session["intro_seen"] = True
        intro_animation = True

    fade_in = session.pop("fade_in", False)

    hints = get_hints(pokemon, hint_index)

    is_daily = session.get("is_daily", False)

    return render_template(
        "game.html",
        hints=hints,
        score=score,
        rounds=rounds,
        image_revealed=revealed,
        image_url=pokemon["sprite_url"],
        tiers=TIER_OPTIONS,
        selected_tiers=selected_tiers,
        hint_index=hint_index,
        last_correct=last_correct,
        guess_wrong=guess_wrong,
        bonus_multiplier=bonus_multiplier,
        intro_animation=intro_animation,
        points_earned=points_earned,
        fade_in=fade_in,
        is_daily=is_daily,
        current_date = datetime.now().strftime("%B %d, %Y"),
        show_leaderboard=show_leaderboard,
        show_name_entry=session.get("show_name_entry", False)
    )

@app.route("/guess", methods=["POST"])
def guess():
    guess = request.form["guess"].strip().lower()
    pokemon = session.get("pokemon")
    correct_answer = pokemon["name"].lower()
    if guess == correct_answer:
        session["revealed"] = True
        earned_points = calculate_points()
        session["score"] = session.get("score", 0) + earned_points
        session["rounds"] = session.get("rounds", 0) + 1
        session["last_correct"] = True
        if session.get("is_daily", False):
            time_taken = datetime.now().timestamp() - session.get("start_time", datetime.now().timestamp())
            session["time_taken"] = time_taken
            session["pending_score"] = session["score"]
            session["show_name_entry"] = True
        session["points_earned"] = earned_points
        session["guess_wrong"] = False
        session["bonus_multiplier"] = (earned_points > 100)  # True if x1.5 was applied
    else:
        session["hint_index"] = session.get("hint_index", 0) + 1
        session["guess_wrong"] = True
    return redirect(url_for("game"))

@app.route("/daily")
def daily_challenge():
    today = datetime.now().strftime("%Y-%m-%d")
    pokemon_list = [p for p in all_pokemon if p["Tier"] in TIER_OPTIONS and p["Tier"] != "Unranked"]

    seed = sum(ord(c) for c in today)
    random.seed(seed)
    daily_pokemon = random.choice(pokemon_list)

    session.clear()
    session["pokemon"] = daily_pokemon
    session["is_daily"] = True
    session["score"] = 0
    session["rounds"] = 0
    session["hint_index"] = 0
    session["start_time"] = datetime.now().timestamp()
    session["revealed"] = False
    session["last_correct"] = False

    return redirect(url_for("game"))

@app.route("/leaderboard")
def leaderboard():
    today = datetime.now().strftime("%Y-%m-%d")
    
    if os.path.exists(DAILY_LEADERBOARD_FILE):
        with open(DAILY_LEADERBOARD_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {}

    scores = data.get(today, [])
    return jsonify(scores)

@app.route("/next")
def next_pokemon():
    if session.get("is_daily"):
        session.pop("is_daily")
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

@app.route("/restart", methods=["POST"])
def restart():
    session.clear()
    return redirect(url_for("game"))

@app.route("/update_tiers", methods=["POST"])
def update_tiers():
    selected = request.form.getlist("tiers")
    if selected:
        session["tiers"] = selected
    else:
        session["tiers"] = ["OU"]
    pick_new_pokemon()
    session["fade_in"] = True
    return redirect(url_for("game"))

@app.route("/submit_name", methods=["POST"])
def submit_name():
    player_name = request.form.get("player_name", "Anonymous")
    pending_score = session.pop("pending_score", None)
    time_taken = session.pop("time_taken", None)

    if pending_score is not None and time_taken is not None:
        save_daily_score(player_name, pending_score, time_taken)

    session["player_name"] = player_name
    session.pop("show_name_entry", None)
    session.pop("is_daily", None)

    session["score"] = 0 
    session["rounds"] = 0
    session["show_leaderboard"] = True
    return redirect(url_for("game"))

if __name__ == "__main__":
    app.run(debug=True)
