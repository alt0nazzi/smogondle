from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from datetime import datetime
import json
import random
from difflib import get_close_matches
import os
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from shop_items import SHOP_ITEMS
import re

app = Flask(__name__)
app.secret_key = 'supersecretkey'

login_manager = LoginManager()
login_manager.init_app(app)

def get_db():
    conn = sqlite3.connect("smogondle.db")
    conn.row_factory = sqlite3.Row
    return conn

with open("all_pokemon_with_tiers.json", "r", encoding="utf-8") as f:
    all_pokemon = json.load(f)

TIER_OPTIONS = sorted(set(p["Tier"] for p in all_pokemon if p["Tier"] != "Unranked"))

DAILY_LEADERBOARD_FILE = "daily_leaderboard.json"

ACHIEVEMENTS = {
    "first_win": {
        "name": "First Win",
        "condition": lambda u: u["score"] >= 10,
        "progress": lambda u: (u["score"], 10),
        "description": "Score 10 total points, winning your first game of Smogondle"
    },
    "1000_points": {
        "name": "1000 Points",
        "condition": lambda u: u["score"] >= 1000,
        "progress": lambda u: (u["score"], 1000),
        "description": "Earn a total of 1,000 points"
    },
    "10000_points": {
        "name": "10K Club",
        "condition": lambda u: u["score"] >= 10000,
        "progress": lambda u: (u["score"], 10000),
        "description": "Earn a total of 10,000 points"
    },
    "100000_points": {
        "name": "100K Club",
        "condition": lambda u: u["score"] >= 100000,
        "progress": lambda u: (u["score"], 100000),
        "description": "Earn a total of 100,000 points"
    },
    "250000_points": {
        "name": "Quarter Million",
        "condition": lambda u: u["score"] >= 250000,
        "progress": lambda u: (u["score"], 250000),
        "description": "Earn 250,000 total points"
    },
    "500000_points": {
        "name": "Halfway Hero",
        "condition": lambda u: u["score"] >= 500000,
        "progress": lambda u: (u["score"], 500000),
        "description": "Earn 500,000 total points"
    },
    "750000_points": {
        "name": "Grind Legend",
        "condition": lambda u: u["score"] >= 750000,
        "progress": lambda u: (u["score"], 750000),
        "description": "Earn 750,000 total points"
    },
    "1000000_points": {
        "name": "Million-Point Club",
        "condition": lambda u: u["score"] >= 1000000,
        "progress": lambda u: (u["score"], 1000000),
        "description": "A milli a milli a milli a milli a mil-"
    },
    "shop_collector_1": {
        "name": "Capitalist",
        "condition": lambda u: len(u.get("inventory", [])) >= 1,
        "progress": lambda u: (len(u.get("inventory", [])), 1),
        "description": "Purchase your first cosmetic item from the shop"
    },
    "shop_collector_10": {
        "name": "Collector - Tier I",
        "condition": lambda u: len(u.get("inventory", [])) >= 10,
        "progress": lambda u: (len(u.get("inventory", [])), 10),
        "description": "Purchase 10 cosmetic items from the shop"
    },
    "shop_collector_25": {
        "name": "Collector - Tier II",
        "condition": lambda u: len(u.get("inventory", [])) >= 25,
        "progress": lambda u: (len(u.get("inventory", [])), 25),
        "description": "Purchase 25 cosmetic items from the shop"
    },
    "shop_collector_50": {
        "name": "Collector - Tier III",
        "condition": lambda u: len(u.get("inventory", [])) >= 50,
        "progress": lambda u: (len(u.get("inventory", [])), 50),
        "description": "Purchase 50 cosmetic items from the shop"
    },
    "equip_avatar": {
        "name": "No Longer Anon",
        "condition": lambda u: u.get("avatar") not in [None, "", "default"],
        "progress": lambda u: (1 if u.get("avatar") else 0, 1),
        "description": "Equip your first avatar"
    },
    "equip_badge": {
        "name": "Badge of Honor",
        "condition": lambda u: len(u.get("badges_equipped", [])) > 0,
        "progress": lambda u: (len(u.get("badges_equipped", [])), 1),
        "description": "Equip your first badge"
    },
    "equip_theme": {
        "name": "Leaving Space",
        "condition": lambda u: u.get("theme") not in [None, "", "default"],
        "progress": lambda u: (1 if u.get("theme") else 0, 1),
        "description": "Equip your first theme"
    },
    "equip_title": {
        "name": "Finding Meaning",
        "condition": lambda u: u.get("title") not in [None, "", "default", "New Challenger"],
        "progress": lambda u: (1 if u.get("title") else 0, 1),
        "description": "Equip your first title"
    },
    "streak": {
        "name": "Week Streak",
        "condition": lambda u: u["streak"] >= 2,
        "progress": lambda u: (u["streak"], 7),
        "description": "Get 2+ Daily Challenge wins in a row"
    },
    "speed_demon": {
        "name": "Speed Demon",
        "condition": lambda u: u.get("round_time", 999) < 5,
        "progress": lambda u: (1 if u.get("round_time", 999) < 5 else 0, 1),
        "description": "After starting a new round, guess correctly in under 5 seconds"
    },
    "one_shot_wonder": {
        "name": "One Shot Wonder",
        "condition": lambda u: u.get("hint_index") == 0 and not u.get("guess_wrong", False),
        "progress": lambda u: (1 if u.get("hint_index") == 0 and not u.get("guess_wrong", False) else 0, 1),
        "description": "Guess correctly without revealing any additional hints"
    },
    "flawless_5": {
        "name": "Flawless 5",
        "condition": lambda u: u.get("hint_index", 0) <= 1 and u.get("flawless_chain", 0) >= 5,
        "progress": lambda u: (u.get("flawless_chain", 0), 5),
        "description": "5 wins in a row using only the default Tier + Types hints"
    },
    "no_mercy": {
        "name": "No Mercy",
        "condition": lambda u: u.get("no_misses_chain", 0) >= 3,
        "progress": lambda u: (u.get("no_misses_chain", 0), 3),
        "description": "Win 3 rounds in a row with 0 incorrect guesses"
    },
    "no_retreat": {
        "name": "No Retreat",
        "condition": lambda u: u.get("no_misses_chain", 0) >= 10,
        "progress": lambda u: (u.get("no_misses_chain", 0), 10),
        "description": "Win 10 rounds in a row with 0 incorrect guesses"
    },
    "raw_talent": {
        "name": "Raw Talent",
        "condition": lambda u: u.get("no_misses_chain", 0) >= 50,
        "progress": lambda u: (u.get("no_misses_chain", 0), 50),
        "description": "Win 50 rounds in a row with 0 incorrect guesses"
    },
    "savant": {
        "name": "Savant",
        "condition": lambda u: u.get("no_misses_chain", 0) >= 100,
        "progress": lambda u: (u.get("no_misses_chain", 0), 100),
        "description": "Win 100 rounds in a row with 0 incorrect guesses"
    },
    "tier_novice_uber": {
        "name": "Tier Novice - Uber",
        "condition": lambda u: u.get("tier_tracker", {}).get("Uber", 0) >= 10,
        "progress": lambda u: (u.get("tier_tracker", {}).get("Uber", 0), 10),
        "description": "Guess 10 Uber-tier Pokémon correctly"
    },
    "tier_master_uber": {
        "name": "Tier Master - Uber",
        "condition": lambda u: u.get("tier_tracker", {}).get("Uber", 0) >= 100,
        "progress": lambda u: (u.get("tier_tracker", {}).get("Uber", 0), 100),
        "description": "Guess 100 Uber-tier Pokémon correctly"
    },
    "tier_novice_ou": {
        "name": "Tier Novice - OU",
        "condition": lambda u: u.get("tier_tracker", {}).get("OU", 0) >= 10,
        "progress": lambda u: (u.get("tier_tracker", {}).get("OU", 0), 10),
        "description": "Guess 10 OU-tier Pokémon correctly"
    },
    "tier_master_ou": {
        "name": "Tier Master - OU",
        "condition": lambda u: u.get("tier_tracker", {}).get("OU", 0) >= 100,
        "progress": lambda u: (u.get("tier_tracker", {}).get("OU", 0), 100),
        "description": "Guess 100 OU-tier Pokémon correctly"
    },
    "tier_novice_uu": {
        "name": "Tier Novice - UU",
        "condition": lambda u: u.get("tier_tracker", {}).get("UU", 0) >= 10,
        "progress": lambda u: (u.get("tier_tracker", {}).get("UU", 0), 10),
        "description": "Guess 10 UU-tier Pokémon correctly"
    },
    "tier_master_uu": {
        "name": "Tier Master - UU",
        "condition": lambda u: u.get("tier_tracker", {}).get("UU", 0) >= 100,
        "progress": lambda u: (u.get("tier_tracker", {}).get("UU", 0), 100),
        "description": "Guess 100 UU-tier Pokémon correctly"
    },
    "tier_novice_nu": {
        "name": "Tier Novice - NU",
        "condition": lambda u: u.get("tier_tracker", {}).get("NU", 0) >= 10,
        "progress": lambda u: (u.get("tier_tracker", {}).get("NU", 0), 10),
        "description": "Guess 10 NU-tier Pokémon correctly"
    },
    "tier_master_nu": {
        "name": "Tier Master - NU",
        "condition": lambda u: u.get("tier_tracker", {}).get("NU", 0) >= 100,
        "progress": lambda u: (u.get("tier_tracker", {}).get("NU", 0), 100),
        "description": "Guess 100 NU-tier Pokémon correctly"
    },
    "tier_novice_pu": {
        "name": "Tier Master - PU",
        "condition": lambda u: u.get("tier_tracker", {}).get("PU", 0) >= 10,
        "progress": lambda u: (u.get("tier_tracker", {}).get("PU", 0), 10),
        "description": "Guess 10 PU-tier Pokémon correctly"
    },
    "tier_master_pu": {
        "name": "Tier Master - PU",
        "condition": lambda u: u.get("tier_tracker", {}).get("PU", 0) >= 100,
        "progress": lambda u: (u.get("tier_tracker", {}).get("PU", 0), 100),
        "description": "Guess 100 PU-tier Pokémon correctly"
    },
    "all_tier_explorer": {
        "name": "All-Tier Explorer",
        "condition": lambda u: all(tier in u.get("tier_tracker", {}) and u["tier_tracker"][tier] > 0 for tier in TIER_OPTIONS),
        "progress": lambda u: (
            sum(1 for tier in TIER_OPTIONS if u.get("tier_tracker", {}).get(tier, 0) > 0),
            len(TIER_OPTIONS)
        ),
        "description": "Guess at least one Pokémon from every tier"
    },
    "type_tracker": {
        "name": "Type Tracker",
        "condition": lambda u: len(set(u.get("type_tracker", []))) == 18,
        "progress": lambda u: (len(set(u.get("type_tracker", []))), 18),
        "description": "Correctly guess at least one Pokémon of every type"
    },
    "not_a_pokemon": {
        "name": "404 Not a Pokémon",
        "condition": lambda u: u.get("not_found_guesses", 0) >= 1,
        "progress": lambda u: (u.get("not_found_guesses", 0), 1),
        "description": "Guess a name that isn't a real Pokémon"
    },
    "missingno_hunter": {
        "name": "MissingNo. Hunter",
        "condition": lambda u: u.get("not_found_guesses", 0) >= 10,
        "progress": lambda u: (u.get("not_found_guesses", 0), 10),
        "description": "Attempt 10 guesses that are not recognized Pokémon"
    },
    "palindrome_master": {
        "name": "Palindrome Master",
        "condition": lambda u: u.get("palindrome_guesses", 0) >= 3,
        "progress": lambda u: (u.get("palindrome_guesses", 0), 3),
        "description": "Correctly guess 3 Pokémon whose names are palindromes"
    },
    "hint_hoarder": {
        "name": "Hint Hoarder",
        "condition": lambda u: u.get("max_hints_used", 0) >= 5,
        "progress": lambda u: (1 if u.get("max_hints_used", 0) >= 5 else 0, 1),
        "description": "Win a round after revealing all available hints"
    },
    "zero_to_hero": {
        "name": "Zero to Hero",
        "condition": lambda u: u.get("hint_index", 0) >= 5 and not u.get("guess_wrong", False),
        "progress": lambda u: (1 if u.get("hint_index", 0) >= 5 and not u.get("guess_wrong", False) else 0, 1),
        "description": "Win a round using the final hint without making a single mistake"
    }
}

if os.path.exists(DAILY_LEADERBOARD_FILE):
    with open(DAILY_LEADERBOARD_FILE, "r") as f:
        daily_leaderboard = json.load(f)
else:
    daily_leaderboard = {}

PROFANE_WORDS = {"admin", "mod", "fuck", "shit", "bitch", "slut", "nigger", "cunt", "asshole", "dick", "pussy", "fag", "cock", "whore", "cum", "rape", "hitler", "nazi", "kike", "twat"}  # expand this as needed - thanks ChatGPT lmao

def contains_profanity(username):
    lowered = username.lower()
    return any(bad in lowered for bad in PROFANE_WORDS)

def contains_malicious_chars(username):
    return bool(re.search(r"[<>\"'%;(){}]", username)) or "--" in username

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

def calculate_pokedollars():
    # Mimic the logic from calculate_points()
    hint_index = session.get("hint_index", 0)
    revealed_hints = hint_index

    if revealed_hints == 0:
        base_pokedollars = 150
    elif revealed_hints == 1:
        base_pokedollars = 120
    elif revealed_hints == 2:
        base_pokedollars = 90
    elif revealed_hints == 3:
        base_pokedollars = 60
    elif revealed_hints == 4:
        base_pokedollars = 30
    else:
        base_pokedollars = 15

    if revealed_hints < 4:
        multiplier = 1.0
    else:
        multiplier = 1.0

    return int(base_pokedollars * multiplier)

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
        strategy_group = []
        for s in pokemon["strategies"]:
            lines = []
            if s.get("ability"): lines.append(f"<strong>Ability:</strong> {s['ability']}")
            if s.get("moveslots"):
                moves_list = "".join(f"<li>{move}</li>" for move in s["moveslots"])
                lines.append(f"<strong>Moves:</strong><ul style='list-style: disc inside;'>{moves_list}</ul>")
            if s.get("item"): lines.append(f"<strong>Item:</strong> {s['item']}")
            if s.get("nature"): lines.append(f"<strong>Nature:</strong> {s['nature']}")
            if s.get("evs"): lines.append(f"<strong>EVs:</strong> {s['evs']}")
            if s.get("tera_type"): lines.append(f"<strong>Tera Type:</strong> {s['tera_type']}")
            full_html = "<br>".join(lines)
            strategy_group.append({
                "label": s.get("name", "Strategy"),
                "html": full_html
            })
        if strategy_group:
            dynamic_hints.append({
                "label": "Smogon Strategies",
                "type": "strategy",
                "strategies": strategy_group
            })
    else:
        dynamic_hints.append({
            "label": "Strategy",
            "html": "<em>This Pokémon has no applicable Smogon strategies.</em>",
            "tier_overlay": pokemon["Tier"]
        })

    gen_info = pokemon.get("generation", "")
    gen_suffix = f' <span class="text-gray-400 text-sm">(introduced in <i>{gen_info}</i>)</span>' if gen_info else ""
    dynamic_hints.append({
        "label": "ID",
        "text": f'{pokemon["id"]}{gen_suffix}'
    })

    return static_hints + dynamic_hints[:hint_index]

@app.route("/")
def index():
    return redirect(url_for("game"))

@app.route("/game")
def game():
    user_data = {"tier_tracker": {}}
    ACHIEVEMENTS_REV = {v["name"]: v for k, v in ACHIEVEMENTS.items()}
    if "pokemon" not in session:
        pick_new_pokemon()
        if "start_time" not in session:
            session["start_time"] = datetime.now().timestamp()
    pokemon = session["pokemon"]

    score = session.get("score", 0)
    rounds = session.get("rounds", 0)
    show_leaderboard = session.pop('show_leaderboard', False)
    daily_already_played = session.pop("daily_already_played", False)
    revealed = session.get("revealed", False)
    selected_tiers = session.get("tiers", [])
    hint_index = session.get("hint_index", 0)
    last_correct = session.get("last_correct", False)
    guess_wrong = session.pop("guess_wrong", False)
    bonus_multiplier = session.pop("bonus_multiplier", False)
    points_earned = session.pop("points_earned", 0)
    intro_animation = False
    trigger_reward_glow = session.pop("trigger_reward_glow", False)
    gave_up_answer = session.pop("gave_up_answer", None)

    if "intro_seen" not in session:
        session["intro_seen"] = True
        intro_animation = True

    fade_in = session.pop("fade_in", False)

    hints = get_hints(pokemon, hint_index)

    is_daily = session.get("is_daily", False)

    progress_data = {}

    if current_user.is_authenticated:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT streak, total_score, tier_tracker, type_tracker, pokedollars FROM users WHERE id = ?", (current_user.id,))
        row = cur.fetchone()
        if row:
            current_user.streak = row[0]
            current_user.total_score = row[1]
            current_user.tier_tracker = row[2]
            current_user.type_tracker = row[3]
            current_user.pokedollars = row["pokedollars"]
        else:
            current_user.streak = 0
            current_user.total_score = 0
            current_user.tier_tracker = "{}"

        cur.execute("SELECT achievement_code, date_awarded FROM user_achievements WHERE user_id = ?", (current_user.id,))
        rows = cur.fetchall()
        achievement_dict = {ACHIEVEMENTS[a]["name"]: d for a, d in rows if a in ACHIEVEMENTS}

        current_user.achievements = json.dumps(achievement_dict)
        conn.close()
        if row:
            current_user.streak = row[0]

        user_data = {
            "score": current_user.total_score,
            "streak": current_user.streak,
            "tier_tracker": json.loads(current_user.tier_tracker or "{}"),
            "type_tracker": json.loads(getattr(current_user, "type_tracker", "[]") or "[]"),
        }

        first_win_unlocked = "First Win" in achievement_dict
        if not first_win_unlocked:
            session["auto_advance"] = False
        else:
            if "auto_advance" not in session:
                session["auto_advance"] = True

        progress_data = {}
        user_data["inventory"] = json.loads(getattr(current_user, "inventory", "[]") or "[]")
        for key, ach in ACHIEVEMENTS.items():
            earned = key in json.loads(current_user.achievements or "{}")
            if not earned and "progress" in ach:
                current, total = ach["progress"](user_data)
                progress_data[ach["name"]] = {
                    "current": current,
                    "total": total
                }

    new_achievements = session.pop("new_achievements", [])

    return render_template(
        "game.html",
        hints=hints,
        score=score,
        pokedollars_earned=session.pop("pokedollars_earned", 0),
        pokedollars_total=session.get("pokedollars_total", 0),
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
        new_achievements=new_achievements,
        ACHIEVEMENTS_REV=ACHIEVEMENTS_REV,
        progress_data=progress_data,
        show_leaderboard=show_leaderboard,
        show_name_entry=session.get("show_name_entry", False),
        user=current_user if current_user.is_authenticated else None,
        user_achievements=json.loads(current_user.achievements or "{}") if current_user.is_authenticated else {},
        user_streak=current_user.streak if current_user.is_authenticated else 0,
        daily_already_played=daily_already_played,
        trigger_reward_glow=trigger_reward_glow,
        tier_tracker=user_data["tier_tracker"],
        is_perfect=session.pop("is_perfect", False),
        new_hint_label=session.pop("new_hint_label", None),
        gave_up=session.pop("gave_up", False),
        gave_up_reveal=session.pop("gave_up_reveal", False),
        gave_up_answer=gave_up_answer,
        show_first_win_popup=session.pop("show_first_win_popup", False)
    )

@app.route("/guess", methods=["POST"])
def guess():
    guess = request.form["guess"].strip().lower()
    pokemon = session.get("pokemon")
    correct_answer = pokemon["name"].lower()
    today = datetime.now().strftime("%Y-%m-%d")
    new_achievements = []

    if guess == correct_answer:
        earned_points = calculate_points()
        earned_pokedollars = calculate_pokedollars()

        # Multiply both by 10 if it's the Daily Challenge
        if session.get("is_daily", False):
            earned_points *= 10
            earned_pokedollars *= 10
        session["pokedollars_total"] = session.get("pokedollars_total", 0) + earned_pokedollars
        session["score"] = session.get("score", 0) + earned_points
        session["rounds"] = session.get("rounds", 0) + 1
        session["last_correct"] = True
        session["trigger_reward_glow"] = True

        # Timing for Speed Demon
        current_time = datetime.now().timestamp()
        start_time = session.get("start_time", current_time)
        duration = current_time - start_time
        session["round_time"] = duration

        # Tier for Tier Master
        current_tier = pokemon["Tier"]
        tier_tracker = session.get("tier_tracker", {})
        if current_tier in TIER_OPTIONS:
            tier_tracker[current_tier] = tier_tracker.get(current_tier, 0) + 1
            session["tier_tracker"] = tier_tracker

        # Track types for Type Tracker
        type_tracker = session.get("type_tracker", [])
        new_types = [t for t in pokemon["types"] if t not in type_tracker]
        if new_types:
            type_tracker.extend(new_types)
            session["type_tracker"] = type_tracker

        # Track palindromes
        if guess == guess[::-1]:
            session["palindrome_guesses"] = session.get("palindrome_guesses", 0) + 1

        # Track if all hints were used (hint_index == max)
        if session.get("hint_index", 0) >= len(get_hints(pokemon, 999)) - 1:
            session["max_hints_used"] = 5  # mark it as having reached the maximum

        # Track hint index and wrong guesses
        hint_index = session.get("hint_index", 0)
        guess_wrong = session.get("guess_wrong", False)
        session["is_perfect"] = hint_index == 0 and not guess_wrong # Alec note: Used for animations
        session["correct_first_hint"] = (hint_index == 0) # Alec note: Used for achievement-awarding logic 
        session["no_hints"] = (hint_index == 0 and session.get("guess_wrong", False) == False)
        if session.get("guess_wrong", False):
            session["flawless_chain"] = 0
        elif hint_index <= 1:
            session["flawless_chain"] = session.get("flawless_chain", 0) + 1
        else:
            session["flawless_chain"] = 0
        session["no_misses_chain"] = session.get("no_misses_chain", 0) + (0 if session.get("guess_wrong", False) else 1)

        if session.get("is_daily", False):
            time_taken = datetime.now().timestamp() - session.get("start_time", datetime.now().timestamp())
            session["time_taken"] = time_taken
            pending_score = session["score"]
            if current_user.is_authenticated:
                save_daily_score(current_user.username, pending_score, time_taken)
            else:
                session["show_name_entry"] = True  # ← flag for game.html
            session["show_leaderboard"] = True
            session["is_daily"] = False
            session["rounds"] = 0
        else:
            if current_user.is_authenticated:
                user_id = current_user.id
                conn = get_db()
                cur = conn.cursor()

                # Fetch score, streak
                cur.execute("SELECT total_score, streak FROM users WHERE id = ?", (user_id,))
                row = cur.fetchone()
                conn.close()
                if not row:
                    return redirect(url_for("game"))

                total_score, streak = row
                total_score += earned_points

                # Update score in database
                conn = get_db()
                cur = conn.cursor()
                cur.execute("UPDATE users SET total_score = ? WHERE id = ?", (total_score, user_id))
                conn.commit()

                # Fetch and update Pokédollars
                cur.execute("SELECT pokedollars FROM users WHERE id = ?", (user_id,))
                row = cur.fetchone()
                current_pokedollars = row[0] if row and row[0] is not None else 0
                new_total = current_pokedollars + earned_pokedollars

                cur.execute("UPDATE users SET pokedollars = ? WHERE id = ?", (new_total, user_id))
                conn.commit()

                # Re-fetch session data needed for achievement checks
                hint_index = session.get("hint_index", 0)
                round_time = session.get("round_time", 0)
                flawless_chain = session.get("flawless_chain", 0)
                no_misses_chain = session.get("no_misses_chain", 0)
                tier_tracker = session.get("tier_tracker", {})

                # Save tier_tracker to users table (as JSON string) if not already done
                cur.execute("SELECT tier_tracker FROM users WHERE id = ?", (user_id,))
                tracker_row = cur.fetchone()
                existing_tracker = json.loads(tracker_row[0]) if tracker_row and tracker_row[0] else {}

                # Merge session tracker into DB tracker
                merged_tracker = existing_tracker.copy()
                for k, v in tier_tracker.items():
                    merged_tracker[k] = max(merged_tracker.get(k, 0), v)

                # Save merged tracker
                cur.execute("UPDATE users SET tier_tracker = ? WHERE id = ?", (json.dumps(merged_tracker), user_id))
                conn.commit()

                # Update session copy as well
                session["tier_tracker"] = merged_tracker

                # Save type_tracker to DB (convert to JSON array)
                cur.execute("SELECT type_tracker FROM users WHERE id = ?", (user_id,))
                type_row = cur.fetchone()
                existing_types = json.loads(type_row[0]) if type_row and type_row[0] else []

                combined_types = list(set(existing_types + session.get("type_tracker", [])))
                cur.execute("UPDATE users SET type_tracker = ? WHERE id = ?", (json.dumps(combined_types), user_id))
                conn.commit()
                session["type_tracker"] = combined_types  # Refresh session with latest

                # Add session data into user_data
                user_data = {"score": total_score, "streak": streak}
                user_data.update({
                    "hint_index": hint_index,
                    "round_time": round_time,
                    "flawless_chain": flawless_chain,
                    "no_misses_chain": no_misses_chain,
                    "tier_tracker": merged_tracker,
                    "not_found_guesses": session.get("not_found_guesses", 0),
                    "palindrome_guesses": session.get("palindrome_guesses", 0),
                    "max_hints_used": session.get("max_hints_used", 0)
                })

                # Check achievements
                cur.execute("SELECT achievement_code FROM user_achievements WHERE user_id = ?", (user_id,))
                unlocked = {row[0] for row in cur.fetchall()}

                new_achievements = []

                for key, data in ACHIEVEMENTS.items():
                    if key not in unlocked and data["condition"](user_data):
                        cur.execute("INSERT INTO user_achievements (user_id, achievement_code, date_awarded) VALUES (?, ?, ?)",
                                    (user_id, key, today))
                        new_achievements.append(data["name"])

                conn.commit()
                conn.close()

                if new_achievements:
                    session["new_achievements"] = new_achievements

                    if "First Win" in new_achievements:
                        session["auto_advance"] = True
                        session["show_first_win_popup"] = True

        session["new_achievements"] = new_achievements
        session["points_earned"] = earned_points
        session["pokedollars_earned"] = earned_pokedollars
        session["guess_wrong"] = False
        session["bonus_multiplier"] = (earned_points > 100)
        if not session.get("is_daily"):
            session["revealed"] = True  # Always show the Pokémon image
            if session.get("auto_advance", True):
                pick_new_pokemon()
                session["hint_index"] = 0
                session["start_time"] = datetime.now().timestamp()
                session["revealed"] = False  # Will be shown again on next round

    else:
        current_index = session.get("hint_index", 0)
        hints_before = get_hints(session["pokemon"], current_index)
        max_hints = len(get_hints(session["pokemon"], 999))

        if current_index < max_hints:
            session["hint_index"] = current_index + 1
            hints_after = get_hints(session["pokemon"], session["hint_index"])
            if len(hints_after) > len(hints_before):
                session["new_hint_label"] = hints_after[-1]["label"]
            else:
                session["new_hint_label"] = "NoMoreHints"
        else:
            session["new_hint_label"] = "NoMoreHints"
        session["last_correct"] = False
        session["guess_wrong"] = True
        # Track guesses that aren't valid Pokémon
        names_lower = [p["name"].lower() for p in all_pokemon]
        if guess not in names_lower:
            session["not_found_guesses"] = session.get("not_found_guesses", 0) + 1

    return redirect(url_for("game"))

@app.route("/daily")
def daily_challenge():
    today = datetime.now().strftime("%Y-%m-%d")

    if current_user.is_authenticated:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM daily_attempts WHERE user_id = ? AND date = ?", (current_user.id, today))
        if cur.fetchone():
            conn.close()
            session["daily_already_played"] = True
            return redirect(url_for("game"))

        cur.execute("INSERT INTO daily_attempts (user_id, date) VALUES (?, ?)", (current_user.id, today))
        conn.commit()
        conn.close()

    # generate deterministic challenge regardless of login
    seed = sum(ord(c) for c in today)
    random.seed(seed)
    daily_pokemon = random.choice([p for p in all_pokemon if p["Tier"] in TIER_OPTIONS and p["Tier"] != "Unranked"])

    # reset session state
    keys_to_clear = ["pokemon", "score", "rounds", "hint_index", "start_time",
                     "revealed", "last_correct", "pending_score", "time_taken",
                     "guess_wrong", "bonus_multiplier", "seen_pokemon_ids"]
    for k in keys_to_clear:
        session.pop(k, None)

    session.update({
        "pokemon": daily_pokemon,
        "is_daily": True,
        "score": 0,
        "rounds": 0,
        "hint_index": 0,
        "start_time": datetime.now().timestamp(),
        "revealed": False,
        "last_correct": False
    })

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
    session["hint_index"] = 0
    session["start_time"] = datetime.now().timestamp()
    session["revealed"] = False
    session["last_correct"] = False
    session["bonus_multiplier"] = False
    session["points_earned"] = 0
    session["pokedollars_earned"] = 0
    session.pop("gave_up_reveal", None)
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

    seen_ids = session.get("seen_pokemon_ids", [])

    unseen = [p for p in filtered if p["id"] not in seen_ids]

    if unseen:
        chosen = random.choice(unseen)
        seen_ids.append(chosen["id"])
        session["seen_pokemon_ids"] = seen_ids
    else:
        chosen = random.choice(filtered)
        session["seen_pokemon_ids"] = [chosen["id"]]

    session["pokemon"] = chosen
    session["hint_index"] = 0
    session["revealed"] = False

@app.route("/giveup")
def giveup():
    session["last_correct"] = False
    session["image_revealed"] = True
    session["revealed"] = True  # ✅ REQUIRED TO TRIGGER REVEAL IN /game
    session["points_earned"] = 0
    session["pokedollars_earned"] = 0
    session["is_perfect"] = False
    session["guess_wrong"] = True
    session["trigger_reward_glow"] = False
    session["fade_in"] = True
    session["rounds"] = session.get("rounds", 0) + 1
    session["gave_up"] = True
    session["gave_up_reveal"] = True
    session["gave_up_answer"] = session["pokemon"]["name"]

    if session.get("auto_advance", True):
        pick_new_pokemon()
        session["hint_index"] = 0
        session["start_time"] = datetime.now().timestamp()
        session["revealed"] = False
        session["image_revealed"] = False
        session["guess_wrong"] = False
        session["gave_up_reveal"] = False

    return redirect(url_for("game"))

@app.route("/restart", methods=["POST"])
def restart():
    keys_to_keep = {"_user_id", "_fresh", "_id", "is_admin"}
    keys_to_remove = [k for k in session.keys() if k not in keys_to_keep]
    for key in keys_to_remove:
        session.pop(key, None)
    
    # Reset achievement trackers
    for key in ["not_found_guesses", "palindrome_guesses", "max_hints_used"]:
        session.pop(key, None)

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

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # Add profanity and security validation
        if contains_profanity(username):
            error = "That username contains inappropriate language."
        elif contains_malicious_chars(username):
            error = "That username contains invalid characters."
        else:
            conn = sqlite3.connect('smogondle.db', check_same_thread=False)
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cur.fetchone():
                error = "Username already taken."
            else:
                hashed = generate_password_hash(password)
                created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cur.execute("INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)", (username, hashed, created_at))
                conn.commit()
                conn.close()
                return redirect(url_for("login"))
            conn.close()

    return render_template("register.html", error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, username, password, is_admin FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):  # user[2] is hashed password
            user_obj = User(user[0], user[1], user[3])  # include is_admin
            login_user(user_obj)  # Properly log in user using Flask-Login
            session['is_admin'] = bool(user[3])
            return redirect(url_for('game'))
        else:
            error = "Invalid username or password."

    return render_template('login.html', error=error)

@app.route("/logout")
@login_required
def logout():
    session.clear()
    logout_user()
    return redirect(url_for("login"))

class User(UserMixin):
    def __init__(self, id, username, is_admin=False, streak=0, achievements="{}", inventory="[]"):
        self.id = id
        self.username = username
        self.is_admin = is_admin
        self.streak = streak
        self.achievements = achievements
        self.inventory = inventory

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, is_admin, streak, achievements, inventory FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return User(row[0], row[1], row[2], row[3], row[4], row[5])
    return None

@app.route("/profile")
@login_required
def profile():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT username, total_score, streak, theme, badge, avatar, badges_equipped, created_at, title FROM users WHERE id = ?", (current_user.id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return redirect(url_for("game"))

    user_profile = {
        "username": row[0],
        "total_score": row[1],
        "streak": row[2],
        "theme": row[3] or "default",
        "badge": row[4] or "none",
        "avatar": row[5] or "default",
        "badges_equipped": row[6] or "[]",
        "created_at": row[7],
        "title": row[8] or ""
    }

    cur.execute("SELECT inventory FROM users WHERE id = ?", (current_user.id,))
    inv_row = cur.fetchone()
    inventory = []
    if inv_row and inv_row[0]:
        try:
            inventory = json.loads(inv_row[0])
        except json.JSONDecodeError:
            inventory = []

    user_profile["inventory"] = inventory
    conn.close()

    # After loading user_profile and inventory
    title = user_profile.get("title", "")
    title_display = ""
    title_rarity = ""  # <-- define this unconditionally
    if title:
        title_item = next((i for i in inventory if i["type"] == "title" and i["value"] == title), None)
        if title_item:
            title_display = title_item.get("text", title)
            title_rarity = title_item.get("rarity", "")
    badges_equipped = json.loads(user_profile.get("badges_equipped", "[]") or "[]")

    # Resolve images
    avatar = next((i for i in inventory if i["type"] == "avatar" and i["value"] == user_profile["avatar"]), None)
    avatar_image = avatar["image"] if avatar else "/static/default-avatar.png"

    theme = next((i for i in inventory if i["type"] == "theme" and i["value"] == user_profile["theme"]), None)
    background_image = theme["image"] if theme else "/static/themes/default.jpg"
    theme_colors = theme.get("colors", {}) if theme else {}
    is_legendary_theme = (theme.get("rarity") == "legendary") if theme else False
    theme_value = theme.get("value") if theme else ""

    badge_objs = []
    for b in badges_equipped:
        match = next((i for i in inventory if i["type"] == "badge" and i["value"] == b), None)
        if match:
            badge_objs.append(match)

    return render_template("profile.html", profile=user_profile, inventory=inventory,
                        avatar_image=avatar_image, background_image=background_image,
                        equipped_badges=badge_objs,title_display=title_display,
                        title_rarity=title_rarity,theme_colors=theme_colors,
                        is_legendary_theme=is_legendary_theme,theme_value=theme_value)


@app.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    if request.method == "POST":
        theme = request.form.get("theme")
        badge = request.form.get("badge")
        avatar = request.form.get("avatar")

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET theme = ?, badge = ?, avatar = ? WHERE id = ?",
            (theme, badge, avatar, current_user.id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("profile"))

    # Fetch all owned items to populate select options
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT inventory, avatar, badge, theme, badges_equipped FROM users WHERE id = ?", (current_user.id,))
    row = cur.fetchone()
    conn.close()

    inventory = json.loads(row["inventory"] or "[]")
    owned = {(i["type"], i["value"]): i for i in inventory}

    themes = [i for k, i in owned.items() if k[0] == "theme"]
    badges = [i for k, i in owned.items() if k[0] == "badge"]
    avatars = [i for k, i in owned.items() if k[0] == "avatar"]
    titles = [i for k, i in owned.items() if k[0] == "title"]

    return render_template("edit_profile.html",
        themes=themes,
        badges=badges,
        avatars=avatars,
        titles=titles,
        user={
            "theme": row["theme"],
            "avatar": row["avatar"],
            "badge": row["badge"],
            "title": row["title"] if "title" in row.keys() else "",
            "badges_equipped": json.loads(row["badges_equipped"] or "[]")
        }
    )

@app.route("/shop")
@login_required
def shop():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT pokedollars, inventory, avatar, badge, theme FROM users WHERE id = ?", (current_user.id,))
    user_data = cur.fetchone()
    cur.execute("SELECT badges_equipped FROM users WHERE id = ?", (current_user.id,))
    badge_row = cur.fetchone()
    badges_equipped = json.loads(badge_row["badges_equipped"] or "[]") if badge_row else []
    cur.execute("SELECT title FROM users WHERE id = ?", (current_user.id,))
    title_row = cur.fetchone()
    title = title_row["title"] if title_row and title_row["title"] else ""
    conn.close()

    session.pop("pokedollar_flash", None)
    pokedollars = user_data["pokedollars"]
    inventory = json.loads(user_data["inventory"]) if user_data["inventory"] else []
    avatar = user_data["avatar"]
    theme = user_data["theme"]
    insufficient_item = session.pop("insufficient_funds", None)

    # Use set of (type, value) to simplify lookup
    owned = {(item["type"], item["value"]) for item in inventory}

    response = render_template("shop.html",
                               shop_items=SHOP_ITEMS,
                               pokedollars=pokedollars,
                               owned=owned,
                               user=current_user,
                               equipped={"avatar": avatar, "theme": theme, "badges": badges_equipped, "title": title},
                               insufficient_item=insufficient_item,
                               pokedollar_flash=session.get("pokedollar_flash", False))
    session.pop("pokedollar_flash", None)
    return response

@app.route("/purchase", methods=["POST"])
@login_required
def purchase():
    item_type = request.form.get("type")
    item_value = request.form.get("value")

    item = next((i for i in SHOP_ITEMS if i["type"] == item_type and i["value"] == item_value), None)
    if not item:
        return "Item not found", 404

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT pokedollars, inventory FROM users WHERE id = ?", (current_user.id,))
    row = cur.fetchone()
    pokedollars = row["pokedollars"]
    raw_inventory = row["inventory"]
    try:
        inventory = json.loads(raw_inventory)
        if not isinstance(inventory, list):
            inventory = []
    except (TypeError, json.JSONDecodeError):
        inventory = []

    if (item_type, item_value) in {(i["type"], i["value"]) for i in inventory}:
        return "Item already owned", 400

    if pokedollars < item["cost"]:
        session["insufficient_funds"] = item_value  # track which item failed
        return redirect(url_for("shop"))

    pokedollars -= item["cost"]
    inventory.append(item)
    cur.execute("UPDATE users SET pokedollars = ?, inventory = ? WHERE id = ?",
                (pokedollars, json.dumps(inventory), current_user.id))
    conn.commit()

    session["pokedollar_flash"] = True

    # Check for item-based achievements
    cur.execute("SELECT achievement_code FROM user_achievements WHERE user_id = ?", (current_user.id,))
    unlocked = {row[0] for row in cur.fetchall()}

    user_data = {
        "inventory": inventory
    }

    new_achievements = []

    for key, ach in ACHIEVEMENTS.items():
        if key.startswith("shop_") and key not in unlocked and ach["condition"](user_data):
            cur.execute("INSERT INTO user_achievements (user_id, achievement_code, date_awarded) VALUES (?, ?, ?)",
                        (current_user.id, key, datetime.now().strftime("%Y-%m-%d")))
            new_achievements.append(ach["name"])

    conn.commit()

    # Trigger toast notifications
    if new_achievements:
        session["new_achievements"] = new_achievements

    conn.close()
    return redirect(url_for("shop"))

@app.route("/equip_item", methods=["POST"])
@login_required
def equip_item():
    item_type = request.form.get("type")
    item_value = request.form.get("value")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT inventory FROM users WHERE id = ?", (current_user.id,))
    inventory = json.loads(cur.fetchone()["inventory"] or "[]")

    if (item_type, item_value) not in {(i["type"], i["value"]) for i in inventory}:
        return "Item not owned", 400

    if item_type == "badge":
        # Update badges_equipped array
        cur.execute("SELECT badges_equipped FROM users WHERE id = ?", (current_user.id,))
        row = cur.fetchone()
        current_badges = json.loads(row["badges_equipped"] or "[]") if row and row["badges_equipped"] else []

        if item_value in current_badges:
            return redirect(url_for("shop"))  # already equipped

        # Limit to 3 equipped badges
        if len(current_badges) >= 3:
            current_badges.pop(0)  # remove the oldest

        current_badges.append(item_value)

        cur.execute("UPDATE users SET badges_equipped = ? WHERE id = ?", (json.dumps(current_badges), current_user.id))
    else:
        # avatar, theme, title
        cur.execute(f"UPDATE users SET {item_type} = ? WHERE id = ?", (item_value, current_user.id))
    conn.commit()

    # Fetch updated user state
    cur.execute("SELECT avatar, theme, title, badges_equipped FROM users WHERE id = ?", (current_user.id,))
    row = cur.fetchone()

    user_data = {
        "avatar": row["avatar"],
        "theme": row["theme"],
        "title": row["title"],
        "badges_equipped": json.loads(row["badges_equipped"] or "[]")
    }

    # Check for equipment-based achievements
    cur.execute("SELECT achievement_code FROM user_achievements WHERE user_id = ?", (current_user.id,))
    unlocked = {row[0] for row in cur.fetchall()}
    new_achievements = []

    for key in ["equip_avatar", "equip_theme", "equip_title", "equip_badge"]:
        ach = ACHIEVEMENTS[key]
        if key not in unlocked and ach["condition"](user_data):
            cur.execute("INSERT INTO user_achievements (user_id, achievement_code, date_awarded) VALUES (?, ?, ?)",
                        (current_user.id, key, datetime.now().strftime("%Y-%m-%d")))
            new_achievements.append(ach["name"])

    conn.commit()

    # Toasts
    if new_achievements:
        session["new_achievements"] = new_achievements

    conn.close()
    referer = request.form.get("referer") or request.headers.get("Referer")
    if referer and "profile" in referer:
        return redirect(url_for("profile"))
    return redirect(url_for("shop"))

@app.route("/update_badges", methods=["POST"])
@login_required
def update_badges():
    new_badge_order = request.form.getlist("badges[]")
    valid_badges = new_badge_order[:3]

    new_avatar = request.form.get("avatar")
    new_theme = request.form.get("theme")
    new_title = request.form.get("title")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE users
        SET badges_equipped = ?, avatar = ?, theme = ?, title = ?
        WHERE id = ?
    """, (json.dumps(valid_badges), new_avatar, new_theme, new_title, current_user.id))
    conn.commit()
    conn.close()

    return redirect(url_for("profile"))

@app.route("/admin")
@login_required
def admin():
    if not current_user.is_authenticated or not getattr(current_user, "is_admin", False):
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, is_admin, total_score, pokedollars FROM users")
    users = [{"id": row[0], "username": row[1], "score": row[3], "pokedollars": row[4]} for row in cur.fetchall()]
    conn.close()
    return render_template("admin.html", users=users)

@app.route("/delete_user", methods=["POST"])
@login_required
def delete_user():
    if not current_user.is_authenticated or not current_user.is_admin:
        return redirect("/login")

    user_id = request.form.get("user_id")
    if user_id:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
        cur.execute("DELETE FROM user_achievements WHERE user_id = ?", (user_id,))
        cur.execute("DELETE FROM daily_attempts WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

    return redirect("/admin")

@app.route("/update_points", methods=["POST"])
@login_required
def update_points():
    if not current_user.is_authenticated or not current_user.is_admin:
        return redirect("/login")

    user_id = request.form.get("user_id")
    new_points = request.form.get("new_points")

    try:
        new_points = int(new_points)
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE users SET total_score = ? WHERE id = ?", (new_points, user_id))
        conn.commit()
        conn.close()
    except:
        pass

    return redirect("/admin")

@app.route("/update_user_values", methods=["POST"])
@login_required
def update_user_values():
    if not current_user.is_authenticated or not current_user.is_admin:
        return redirect("/login")

    user_id = request.form.get("user_id")
    new_points = request.form.get("new_points")
    new_pokedollars = request.form.get("new_pokedollars")

    try:
        conn = get_db()
        cur = conn.cursor()

        if new_points:
            cur.execute("UPDATE users SET total_score = ? WHERE id = ?", (int(new_points), user_id))
        if new_pokedollars:
            cur.execute("UPDATE users SET pokedollars = ? WHERE id = ?", (int(new_pokedollars), user_id))

        conn.commit()
        conn.close()
    except:
        pass

    return redirect("/admin")

@app.route("/set_auto_advance", methods=["POST"])
def set_auto_advance():
    enabled = request.json.get("enabled", True)
    session["auto_advance"] = enabled
    return jsonify({"status": "ok"})

@app.template_filter('datetimeformat')
def datetimeformat(value, format="%B %d, %Y"):
    if not value:
        return "Unknown"
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime(format)
    except (ValueError, TypeError):
        return str(value)
    
@app.route("/purchase_ajax", methods=["POST"])
@login_required
def purchase_ajax():
    data = request.get_json()
    item_type = data.get("type")
    item_value = data.get("value")

    item = next((i for i in SHOP_ITEMS if i["type"] == item_type and i["value"] == item_value), None)
    if not item:
        return jsonify(status="error", message="Item not found")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT pokedollars, inventory FROM users WHERE id = ?", (current_user.id,))
    row = cur.fetchone()
    pokedollars = row["pokedollars"]
    inventory = json.loads(row["inventory"] or "[]")

    if (item_type, item_value) in {(i["type"], i["value"]) for i in inventory}:
        return jsonify(status="error", message="Item already owned")

    if pokedollars < item["cost"]:
        return jsonify(status="error", message="Insufficient funds")

    pokedollars -= item["cost"]
    inventory.append(item)
    cur.execute("UPDATE users SET pokedollars = ?, inventory = ? WHERE id = ?",
                (pokedollars, json.dumps(inventory), current_user.id))
    conn.commit()
    conn.close()
    return jsonify(status="ok")

@app.errorhandler(401)
def unauthorized_error(error):
    return render_template("401.html"), 401

if __name__ == "__main__":
    app.run(debug=True)
