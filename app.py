from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'
DATABASE = 'slot.db'

def init_db():
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS slot_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            no_bonus_spin INTEGER,
            last_bonus_spin INTEGER,
            second_last_bonus_spin INTEGER,
            today_bet INTEGER,
            last30_bet INTEGER,
            last30_rtp REAL,
            today_rtp REAL,
            score INTEGER,
            status TEXT,
            suggestion TEXT,
            recommended_bet TEXT,
            timestamp TEXT
        )""")
        conn.commit()

def init_event_db():
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS slot_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            stage INTEGER,
            bet INTEGER,
            win INTEGER,
            rtp REAL,
            timestamp TEXT
        )""")
        conn.commit()

def evaluate_status(rtp):
    if rtp >= 1.2:
        return "爆分中"
    elif rtp < 0.9:
        return "吃分中"
    else:
        return "正常區間"

def calculate_score(no_bonus, last_bonus, second_last_bonus, today_rtp, last30_rtp, today_bet, last30_bet):
    score = 0
    if no_bonus > 50:
        score += 1
    if last_bonus > 60:
        score += 1
    if today_rtp < 0.9:
        score += 1
    if today_bet < (last30_bet / 30):
        score += 1
    if last30_rtp > today_rtp:
        score += 1
    return score

def get_suggestion(score):
    if score >= 4:
        return "✅ 推薦遊玩"
    elif score >= 2:
        return "🟡 謹慎觀察"
    else:
        return "⛔ 不建議"

def get_recommended_bet(score, capital):
    if score >= 5:
        return f"{int(capital * 0.15)}～{int(capital * 0.2)} 元（積極進攻）"
    elif score == 4:
        return f"{int(capital * 0.08)}～{int(capital * 0.12)} 元（穩健進攻）"
    elif score == 3:
        return f"{int(capital * 0.05)}～{int(capital * 0.07)} 元（保守試探）"
    else:
        return f"{int(capital * 0.02)}～{int(capital * 0.03)} 元（觀望）"

def get_rtp_trend(rtp_list):
    if len(rtp_list) < 2:
        return "📉 資料不足", "⚠️ 謹慎觀察"
    if rtp_list[-1] > rtp_list[-2] > rtp_list[0]:
        return "📈 明顯上升", "✅ 續玩建議"
    elif rtp_list[-1] < rtp_list[-2] < rtp_list[0]:
        return "📉 連續下降", "⛔ 不建議續玩"
    else:
        return "➡️ 波動穩定", "🟡 小額觀察"

@app.route('/', methods=['GET', 'POST'])
def index():
    suggested_bet = None
    capital = session.get('capital', 0)

    if request.method == 'POST':
        capital = int(request.form.get('capital', capital))
        session['capital'] = capital

        name = request.form['name']
        no_bonus = int(request.form['no_bonus_spin'])
        last_bonus = int(request.form['last_bonus_spin'])
        second_last_bonus = int(request.form['second_last_bonus_spin'])
        today_bet = int(request.form['today_bet'])
        today_rtp = float(request.form['today_rtp'])
        last30_bet = int(request.form['last30_bet'])
        last30_rtp = float(request.form['last30_rtp'])

        status = evaluate_status(today_rtp)
        score = calculate_score(no_bonus, last_bonus, second_last_bonus, today_rtp, last30_rtp, today_bet, last30_bet)
        suggestion = get_suggestion(score)
        recommended_bet = get_recommended_bet(score, capital)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()
            c.execute("""INSERT INTO slot_records (
                name, no_bonus_spin, last_bonus_spin, second_last_bonus_spin,
                today_bet, last30_bet, last30_rtp,
                today_rtp, score, status, suggestion, recommended_bet, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (name, no_bonus, last_bonus, second_last_bonus,
                       today_bet, last30_bet, last30_rtp,
                       today_rtp, score, status, suggestion, recommended_bet, timestamp))
            conn.commit()

        suggested_bet = recommended_bet

    return render_template('index.html', suggested_bet=suggested_bet, capital=capital)

@app.route('/records')
def records():
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM slot_records ORDER BY timestamp DESC")
        rows = c.fetchall()
    return render_template('records.html', records=rows)

@app.route('/bonus_event', methods=['GET', 'POST'])
def bonus_event():
    trend_text = None
    suggestion = None
    rtp_list = []

    if request.method == 'POST':
        name = request.form['name']
        stage = int(request.form['stage'])
        bet = int(request.form['bet'])
        win = int(request.form['win'])
        rtp = round(win / bet, 2) if bet > 0 else 0
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()
            c.execute("""INSERT INTO slot_events (name, stage, bet, win, rtp, timestamp)
                         VALUES (?, ?, ?, ?, ?, ?)""",
                      (name, stage, bet, win, rtp, timestamp))
            conn.commit()

            c.execute("""SELECT rtp FROM slot_events 
                         WHERE name = ? 
                         ORDER BY stage ASC LIMIT 3""", (name,))
            rtp_list = [row[0] for row in c.fetchall()]

        trend_text, suggestion = get_rtp_trend(rtp_list)

    return render_template('bonus_event.html',
                           trend_text=trend_text,
                           suggestion=suggestion,
                           rtp_list=rtp_list)

if __name__ == '__main__':
    init_db()
    init_event_db()
    app.run(debug=True)
