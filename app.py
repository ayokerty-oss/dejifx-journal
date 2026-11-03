import os
import json
import requests
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "forex_journal_secret_2024")

# ── Supabase config ──────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get(
    "SUPABASE_URL",
    "https://tqphrebhsciokzokposm.supabase.co"
)
SUPABASE_KEY = os.environ.get(
    "SUPABASE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRxcGhyZWJoc2Npb2t6b2twb3NtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODMxMDI2OTMsImV4cCI6MjA5ODY3ODY5M30.0YjUG8xrZCFJ0OCgARiTzrix_BWnsvXJyN-zCVPsOo0"
)
TABLE = f"{SUPABASE_URL}/rest/v1/forex_trades"

def _headers(extra=None):
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h

# ── DB helpers ────────────────────────────────────────────────────────────────

def get_all_trades(order="date.desc,created_at.desc"):
    r = requests.get(f"{TABLE}?select=*&order={order}", headers=_headers())
    trades = r.json() if r.ok else []
    for t in trades:
        if isinstance(t.get("mistake_tags"), str):
            try:
                t["mistake_tags"] = json.loads(t["mistake_tags"])
            except Exception:
                t["mistake_tags"] = []
        elif not isinstance(t.get("mistake_tags"), list):
            t["mistake_tags"] = []
    return trades

def get_one_trade(trade_id):
    r = requests.get(f"{TABLE}?id=eq.{trade_id}&select=*", headers=_headers())
    trades = r.json() if r.ok else []
    if not trades:
        return None
    t = trades[0]
    if isinstance(t.get("mistake_tags"), str):
        try:
            t["mistake_tags"] = json.loads(t["mistake_tags"])
        except Exception:
            t["mistake_tags"] = []
    elif not isinstance(t.get("mistake_tags"), list):
        t["mistake_tags"] = []
    return t

def insert_trade(data):
    r = requests.post(TABLE, json=data,
                      headers=_headers({"Prefer": "return=minimal"}))
    return r.status_code in (200, 201)

def update_trade(trade_id, data):
    r = requests.patch(
        f"{TABLE}?id=eq.{trade_id}",
        json=data,
        headers=_headers({"Prefer": "return=minimal"})
    )
    return r.status_code in (200, 204)

def delete_trade_db(trade_id):
    r = requests.delete(f"{TABLE}?id=eq.{trade_id}", headers=_headers())
    return r.status_code in (200, 204)

# ── Constants ─────────────────────────────────────────────────────────────────

PAIRS       = ["GBPCHF", "GBPUSD", "EURUSD", "AUDUSD", "EURCHF", "GBPJPY", "EURJPY", "USDJPY", "XAUUSD"]
SESSIONS    = ["London", "New York", "Asia", "London/NY Overlap"]
SETUP_TYPES = ["FVG_retracement", "OTE", "BOS_FVG", "SSL_sweep_reversal", "BSL_sweep_reversal"]
TRIGGERS    = ["BOS+FVG", "BOS_only", "FVG_only", "OTE", "BOS+OB"]
TIMEFRAMES  = ["1M", "5M", "15M", "1H"]
STOPS       = ["below_swing_low", "below_FVG", "below_OB", "below_CBDR", "below_Asia_Low",
               "above_swing_high", "above_FVG", "above_OB", "above_Asia_High"]
TARGETS     = ["PDH", "PDL", "Asia_High", "Asia_Low", "Weekly_High", "Weekly_Low",
               "STD_-1", "STD_-0.5", "STD_0.5", "STD_1", "STD_-1.5", "STD_1.5", "FVG_fill"]
MISTAKES    = ["no_lq_sweep", "early_entry", "manual_close_early", "against_bias",
               "wrong_zone", "no_fvg_retrace", "traded_into_news", "late_entry", "wrong_session", "overtrading"]
LQ_SWEPT    = ["SSL", "BSL", "Both", "None"]
OUTCOMES    = ["profit", "loss", "breakeven", "pending"]

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    trades = get_all_trades()
    return render_template("index.html", trades=trades)


@app.route("/add", methods=["GET", "POST"])
def add_trade():
    if request.method == "POST":
        f = request.form
        date_str = f.get("date", "")
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            day_of_week = dt.strftime("%A")
        except ValueError:
            day_of_week = ""

        mistake_tags = json.dumps(f.getlist("mistake_tags"))

        trade = {
            "date": date_str,
            "day_of_week": day_of_week,
            "pair": f.get("pair"),
            "session": f.get("session"),
            "htf_bias": f.get("htf_bias"),
            "news_present": 1 if f.get("news_present") == "on" else 0,
            "news_name": f.get("news_name") or None,
            "lq_swept": f.get("lq_swept"),
            "setup_type": f.get("setup_type"),
            "entry_trigger": f.get("entry_trigger"),
            "entry_tf": f.get("entry_tf"),
            "entry_time_nyt": f.get("entry_time_nyt") or None,
            "stop_placement": f.get("stop_placement"),
            "target": f.get("target"),
            "rr_planned": float(f.get("rr_planned") or 0) or None,
            "rr_actual": float(f.get("rr_actual") or 0) or None,
            "pips": float(f.get("pips") or 0) or None,
            "outcome": f.get("outcome"),
            "followed_rules": 1 if f.get("followed_rules") == "on" else 0,
            "mistake_tags": mistake_tags,
            "notes": f.get("notes") or None,
            "source": "manual",
        }
        insert_trade(trade)
        flash("Trade logged ✓", "success")
        return redirect(url_for("index"))

    today = datetime.now().strftime("%Y-%m-%d")
    return render_template("add_trade.html",
        today=today,
        pairs=PAIRS, sessions=SESSIONS, setup_types=SETUP_TYPES,
        triggers=TRIGGERS, timeframes=TIMEFRAMES, stops=STOPS,
        targets=TARGETS, mistakes=MISTAKES, lq_swept_options=LQ_SWEPT,
        outcomes=OUTCOMES)


@app.route("/trade/<int:trade_id>")
def trade_detail(trade_id):
    trade = get_one_trade(trade_id)
    if not trade:
        flash("Trade not found.", "error")
        return redirect(url_for("index"))
    return render_template("trade_detail.html", trade=trade,
        pairs=PAIRS, sessions=SESSIONS, setup_types=SETUP_TYPES,
        triggers=TRIGGERS, timeframes=TIMEFRAMES, stops=STOPS,
        targets=TARGETS, mistakes=MISTAKES, lq_swept_options=LQ_SWEPT,
        outcomes=OUTCOMES)


@app.route("/trade/<int:trade_id>/update", methods=["POST"])
def update_trade_route(trade_id):
    """Update a pending bot-logged trade with actual outcome."""
    f = request.form
    data = {
        "outcome": f.get("outcome"),
        "rr_actual": float(f.get("rr_actual") or 0) or None,
        "pips": float(f.get("pips") or 0) or None,
        "followed_rules": 1 if f.get("followed_rules") == "on" else 0,
        "mistake_tags": json.dumps(f.getlist("mistake_tags")),
        "notes": f.get("notes") or None,
    }
    update_trade(trade_id, data)
    flash("Trade updated ✓", "success")
    return redirect(url_for("index"))


@app.route("/trade/<int:trade_id>/delete", methods=["POST"])
def delete_trade(trade_id):
    delete_trade_db(trade_id)
    flash("Trade deleted.", "info")
    return redirect(url_for("index"))


@app.route("/stats")
def stats():
    trades = get_all_trades(order="date.asc")
    return render_template("stats.html", trades=trades)


@app.route("/api/stats")
def api_stats():
    trades = get_all_trades(order="date.asc")
    # Exclude pending trades from stats
    trades = [t for t in trades if t.get("outcome") != "pending"]

    if not trades:
        return jsonify({"total": 0})

    total    = len(trades)
    wins     = [t for t in trades if t["outcome"] == "profit"]
    losses   = [t for t in trades if t["outcome"] == "loss"]
    be       = [t for t in trades if t["outcome"] == "breakeven"]
    win_rate = round(len(wins) / total * 100, 1)

    rr_vals = [t["rr_actual"] for t in trades if t.get("rr_actual")]
    avg_rr  = round(sum(rr_vals) / len(rr_vals), 2) if rr_vals else None

    pairs = {}
    for t in trades:
        p = t["pair"]
        if p not in pairs:
            pairs[p] = {"wins": 0, "losses": 0, "total": 0}
        pairs[p]["total"] += 1
        if t["outcome"] == "profit":
            pairs[p]["wins"] += 1
        elif t["outcome"] == "loss":
            pairs[p]["losses"] += 1
    pair_wr = {p: round(v["wins"] / v["total"] * 100, 1) for p, v in pairs.items()}

    sessions = {}
    for t in trades:
        s = t["session"]
        if s not in sessions:
            sessions[s] = {"wins": 0, "total": 0}
        sessions[s]["total"] += 1
        if t["outcome"] == "profit":
            sessions[s]["wins"] += 1
    session_wr = {s: round(v["wins"] / v["total"] * 100, 1) for s, v in sessions.items()}

    days = {}
    for t in trades:
        d = t["day_of_week"]
        if d not in days:
            days[d] = {"wins": 0, "total": 0}
        days[d]["total"] += 1
        if t["outcome"] == "profit":
            days[d]["wins"] += 1
    day_wr = {d: round(v["wins"] / v["total"] * 100, 1) for d, v in days.items()}

    mistake_count = {}
    for t in trades:
        for m in (t.get("mistake_tags") or []):
            mistake_count[m] = mistake_count.get(m, 0) + 1

    rule_trades    = [t for t in trades if t["followed_rules"]]
    no_rule_trades = [t for t in trades if not t["followed_rules"]]
    rule_wr    = round(len([t for t in rule_trades if t["outcome"] == "profit"]) / len(rule_trades) * 100, 1) if rule_trades else None
    no_rule_wr = round(len([t for t in no_rule_trades if t["outcome"] == "profit"]) / len(no_rule_trades) * 100, 1) if no_rule_trades else None

    cum_r = []
    running = 0.0
    for t in trades:
        if t.get("rr_actual") is not None:
            if t["outcome"] == "profit":
                running += t["rr_actual"]
            elif t["outcome"] == "loss":
                running -= 1
            cum_r.append({"date": t["date"], "cumR": round(running, 2), "pair": t["pair"]})

    news_trades    = [t for t in trades if t["news_present"]]
    no_news_trades = [t for t in trades if not t["news_present"]]
    news_wr    = round(len([t for t in news_trades if t["outcome"] == "profit"]) / len(news_trades) * 100, 1) if news_trades else None
    no_news_wr = round(len([t for t in no_news_trades if t["outcome"] == "profit"]) / len(no_news_trades) * 100, 1) if no_news_trades else None

    return jsonify({
        "total": total,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(be),
        "win_rate": win_rate,
        "avg_rr": avg_rr,
        "pair_wr": pair_wr,
        "session_wr": session_wr,
        "day_wr": day_wr,
        "mistake_count": mistake_count,
        "rule_wr": rule_wr,
        "no_rule_wr": no_rule_wr,
        "cum_r": cum_r,
        "news_wr": news_wr,
        "no_news_wr": no_news_wr,
        "pair_counts": {p: v["total"] for p, v in pairs.items()},
        "session_counts": {s: v["total"] for s, v in sessions.items()},
    })


if __name__ == "__main__":
    app.run(debug=True, port=5050)
