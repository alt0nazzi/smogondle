from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from datetime import datetime
import json
import random
from difflib import get_close_matches
import os
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

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
    "first_win": {"name": "First Win", "condition": lambda u: u["score"] >= 10},
    "1000_points": {"name": "1000 Points", "condition": lambda u: u["score"] >= 1000},
    "10000_points": {"name": "10000 Points", "condition": lambda u: u["score"] >= 10000},
    "100000_points": {"name": "100000 Points", "condition": lambda u: u["score"] >= 100000},
    "250000_points": {"name": "250000 Points", "condition": lambda u: u["score"] >= 250000},
    "500000_points": {"name": "500000 Points", "condition": lambda u: u["score"] >= 500000},
    "750000_points": {"name": "750000 Points", "condition": lambda u: u["score"] >= 750000},
    "1000000_points": {"name": "Million-Point Club", "condition": lambda u: u["score"] >= 1000000},
    "streak": {"name": "Streak", "condition": lambda u: u["streak"] >= 2}
}

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
            dynamic_hints.append({
                "label": "Strategy",
                "html": full_html,
                "tier_overlay": pokemon["Tier"]
            })
    else:
        dynamic_hints.append({
            "label": "Strategy",
            "html": "<em>This Pokémon has no applicable Smogon strategies.</em>",
            "tier_overlay": pokemon["Tier"]
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
    daily_already_played = session.pop("daily_already_played", False)
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

    if current_user.is_authenticated:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT streak, total_score FROM users WHERE id = ?", (current_user.id,))
        row = cur.fetchone()
        if row:
            current_user.streak = row[0]
            current_user.total_score = row[1]
        else:
            current_user.streak = 0
            current_user.total_score = 0

        cur.execute("SELECT achievement_code, date_awarded FROM user_achievements WHERE user_id = ?", (current_user.id,))
        rows = cur.fetchall()
        achievement_dict = {ACHIEVEMENTS[a]["name"]: d for a, d in rows if a in ACHIEVEMENTS}

        current_user.achievements = json.dumps(achievement_dict)
        conn.close()
        if row:
            current_user.streak = row[0]

    new_achievements = session.pop("new_achievements", [])

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
        new_achievements=new_achievements,
        show_leaderboard=show_leaderboard,
        show_name_entry=session.get("show_name_entry", False),
        user=current_user if current_user.is_authenticated else None,
        user_achievements=json.loads(current_user.achievements or "{}") if current_user.is_authenticated else {},
        user_streak=current_user.streak if current_user.is_authenticated else 0,
        daily_already_played=daily_already_played
    )

@app.route("/guess", methods=["POST"])
def guess():
    guess = request.form["guess"].strip().lower()
    pokemon = session.get("pokemon")
    correct_answer = pokemon["name"].lower()
    today = datetime.now().strftime("%Y-%m-%d")
    new_achievements = []

    if guess == correct_answer:
        session["revealed"] = True
        earned_points = calculate_points()
        session["score"] = session.get("score", 0) + earned_points
        session["rounds"] = session.get("rounds", 0) + 1
        session["last_correct"] = True

        if session.get("is_daily", False):
            time_taken = datetime.now().timestamp() - session.get("start_time", datetime.now().timestamp())
            session["time_taken"] = time_taken
            pending_score = session["score"]

            if current_user.is_authenticated:
                save_daily_score(current_user.username, pending_score, time_taken)

                # Fetch updated achievements
                conn = get_db()
                cur = conn.cursor()
                cur.execute("SELECT achievements FROM users WHERE id = ?", (current_user.id,))
                row = cur.fetchone()
                conn.close()

                if row:
                    achievements_dict = json.loads(row[0] or "{}")
                    for title in achievements_dict:
                        if title not in session.get("seen_achievements", []):
                            new_achievements.append(title)
                    session["seen_achievements"] = list(achievements_dict.keys())

            session["show_leaderboard"] = True
            session["is_daily"] = False
            session["score"] = 0
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

                # Check achievements
                cur.execute("SELECT achievement_code FROM user_achievements WHERE user_id = ?", (user_id,))
                unlocked = {row[0] for row in cur.fetchall()}

                new_achievements = []

                for key, data in ACHIEVEMENTS.items():
                    if key not in unlocked:
                        if data["condition"]({"score": total_score, "streak": streak}):
                            cur.execute("INSERT INTO user_achievements (user_id, achievement_code, date_awarded) VALUES (?, ?, ?)",
                                        (user_id, key, today))
                            new_achievements.append(data["name"])

                conn.commit()
                conn.close()

                if new_achievements:
                    session["new_achievements"] = new_achievements

        session["new_achievements"] = new_achievements
        session["points_earned"] = earned_points
        session["guess_wrong"] = False
        session["bonus_multiplier"] = (earned_points > 100)

    else:
        session["hint_index"] = session.get("hint_index", 0) + 1
        session["last_correct"] = False
        session["guess_wrong"] = True

    return redirect(url_for("game"))

@app.route("/daily")
@login_required
def daily_challenge():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM daily_attempts WHERE user_id = ? AND date = ?", (current_user.id, today))
    if cur.fetchone():
        conn.close()
        session["daily_already_played"] = True
        return redirect(url_for("game"))

    # generate challenge
    seed = sum(ord(c) for c in today)
    random.seed(seed)
    daily_pokemon = random.choice([p for p in all_pokemon if p["Tier"] in TIER_OPTIONS and p["Tier"] != "Unranked"])

    # mark completion
    cur.execute("INSERT INTO daily_attempts (user_id, date) VALUES (?, ?)", (current_user.id, today))
    conn.commit()
    conn.close()

    session.pop("pokemon", None)
    session.pop("score", None)
    session.pop("rounds", None)
    session.pop("hint_index", None)
    session.pop("start_time", None)
    session.pop("revealed", None)
    session.pop("last_correct", None)
    session.pop("pending_score", None)
    session.pop("time_taken", None)
    session.pop("guess_wrong", None)
    session.pop("bonus_multiplier", None)
    session.pop("seen_pokemon_ids", None)
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
    session["revealed"] = True
    session["rounds"] = session.get("rounds", 0) + 1
    return redirect(url_for("game"))

@app.route("/restart", methods=["POST"])
def restart():
    keys_to_keep = {"_user_id", "_fresh", "_id", "is_admin"}
    keys_to_remove = [k for k in session.keys() if k not in keys_to_keep]
    for key in keys_to_remove:
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
        conn = sqlite3.connect('smogondle.db', check_same_thread=False)
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cur.fetchone():
            error = "Username already taken."
        else:
            hashed = generate_password_hash(password)
            cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed))
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
            login_user(user_obj)  # ✅ Properly log in user using Flask-Login
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
    def __init__(self, id, username, is_admin=False, streak=0, achievements="{}"):
        self.id = id
        self.username = username
        self.is_admin = is_admin
        self.streak = streak
        self.achievements = achievements

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, is_admin, streak, achievements FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return User(row[0], row[1], row[2], row[3], row[4])
    return None

@app.route("/admin")
@login_required
def admin():
    if not current_user.is_authenticated or not getattr(current_user, "is_admin", False):
        return redirect("/login")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, is_admin, total_score FROM users")
    users = [{"id": row[0], "username": row[1], "score": row[3]} for row in cur.fetchall()]
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

if __name__ == "__main__":
    app.run(debug=True)
