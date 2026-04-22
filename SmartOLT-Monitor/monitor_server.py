# monitor_server.py
# Backend for Chrome multi-region SmartOLT monitor

import os
import datetime
import json
import winsound
import requests
import time

from flask import Flask, request, jsonify
from flask_cors import CORS

# ---------------- DESKTOP NOTIFICATIONS (Win10 TOAST) ----------------
from win10toast_click import ToastNotifier
toaster = ToastNotifier()

def send_desktop_notification(title: str, message: str):
    try:
        toaster.show_toast(
            title,
            message,
            duration=6,
            icon_path="app_icon.ico",
            threaded=True
        )
        log_system(f"Desktop notification sent: {title}")
    except Exception as e:
        log_system(f"Desktop notification error: {e}")


# ---------------- TELEGRAM CONFIG ----------------
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_config.json")

def load_telegram_config():
    default = {
        "enabled": True,
        "bot_token": "8299720725:AAEV4jqOkeQ_mgx_lFgYpWYts7CxS4RwMX0",
        "chat_ids": [-5095273497],
    }
    try:
        if os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            enabled = bool(data.get("enabled", default["enabled"]))
            bot_token = str(data.get("bot_token", default["bot_token"]))
            chat_ids_raw = data.get("chat_ids", default["chat_ids"])

            if isinstance(chat_ids_raw, str):
                temp = []
                for p in chat_ids_raw.split(","):
                    p = p.strip()
                    if p:
                        try: temp.append(int(p))
                        except: pass
                chat_ids = temp
            else:
                chat_ids = [int(x) for x in chat_ids_raw]

            return enabled, bot_token, chat_ids
    except Exception as e:
        print("Error loading telegram_config.json:", e)

    return default["enabled"], default["bot_token"], default["chat_ids"]


TELEGRAM_ENABLED, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS = load_telegram_config()


# ---------------- FLASK APP ----------------
app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, "Logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# ---------------- LOGS ----------------
MAX_LOG_LINES = 500
notification_log = []
system_log = []

def _ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_notification(msg: str):
    line = f"[{_ts()}] {msg}"
    notification_log.append(line)
    if len(notification_log) > MAX_LOG_LINES:
        del notification_log[:-MAX_LOG_LINES]
    print("NOTIF:", line)

def log_system(msg: str):
    line = f"[{_ts()}] {msg}"
    system_log.append(line)
    if len(system_log) > MAX_LOG_LINES:
        del system_log[:-MAX_LOG_LINES]
    print("SYS:", line)


# ---------------- DEBUG ASCII ----------------
def dump_debug_block(title, regions, new_raw, new_state, last_state, diffs=None):

    lines = []
    lines.append("")
    lines.append("====================================================")
    lines.append(f"DEBUG BLOCK: {title}")
    lines.append("====================================================")

    lines.append("REGIONS (RAW):")
    if not regions:
        lines.append("  (none)")
    else:
        for k, info in regions.items():
            lbl = str(info.get("label"))
            val = str(info.get("value"))
            lines.append(f"  {k}: label='{lbl}', value='{val}'")
    lines.append("")

    lines.append("PARSED (new_raw):")
    lines.append(
        f"  online={new_raw['online']}, total={new_raw['total']}, "
        f"pwrfail={new_raw['pwrfail']}, los={new_raw['los']}, na={new_raw['na']}"
    )
    lines.append("")

    lines.append("PARSED (new_state):")
    lines.append(
        f"  online={new_state['online']}, total={new_state['total']}, "
        f"pwrfail={new_state['pwrfail']}, los={new_state['los']}, na={new_state['na']}"
    )
    lines.append("")

    if last_state is None:
        lines.append("LAST_STATE: None (first run)")
    else:
        lines.append("LAST_STATE:")
        lines.append(
            f"  online={last_state['online']}, total={last_state['total']}, "
            f"pwrfail={last_state['pwrfail']}, los={last_state['los']}, na={last_state['na']}"
        )
    lines.append("")

    if diffs:
        lines.append("DIFFS:")
        for key, value in diffs.items():
            s = "+" if value > 0 else ""
            lines.append(f"  {key}: {s}{value}")
        lines.append("")

    lines.append("END DEBUG BLOCK")
    lines.append("====================================================\n")

    log_system("\n".join(lines))


# ---------------- SOUNDS ----------------
def play_soft_alert():
    wav_path = os.path.join(BASE_DIR, "alert_soft.wav")
    try:
        if os.path.isfile(wav_path):
            winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            winsound.Beep(900, 200)
            winsound.Beep(1100, 220)
    except Exception as e:
        log_system(f"Sound playback error: {e}")


# ---------------- TELEGRAM ----------------
def send_telegram_message(text: str):
    if not TELEGRAM_ENABLED:
        log_system("Telegram disabled")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
            resp = requests.post(url, json=payload, timeout=5)
            if resp.status_code != 200:
                log_system(f"Telegram send failed {chat_id}: {resp.text}")
            else:
                log_system(f"Telegram sent OK to chat {chat_id}")
        except Exception as e:
            log_system(f"Telegram exception {chat_id}: {e}")


# ---------------- UNIFIED ALERT ----------------
def broadcast_event(title, message, telegram_text):
    log_notification(f"{title} — {message}")
    send_desktop_notification(title, message)
    send_telegram_message(telegram_text)


# ---------------- HELPERS ----------------
def safe_int(v):
    try: return int(str(v).strip())
    except: return 0

def extract_number(raw):
    try:
        raw = str(raw).replace(":", " ")
        for p in raw.split():
            if p.isdigit():
                return int(p)
        return 0
    except:
        return 0

def extract_state_from_regions(reg_data):
    online = total = pwr = los = na = 0

    for _, info in reg_data.items():
        lbl = (info.get("label") or "").lower().strip()
        raw = info.get("value")
        val = extract_number(raw)

        if "online" in lbl and "offline" not in lbl:
            online = val
        elif "total" in lbl and "offline" in lbl:
            total = val
        elif "pwr" in lbl or "fail" in lbl:
            pwr = val
        elif "los" in lbl:
            los = val
        elif "n/a" in lbl or lbl == "na":
            na = val

    return {
        "online": online,
        "total": total,
        "pwrfail": pwr,
        "los": los,
        "na": na,
    }

def all_zero(st):
    return st["online"] == st["total"] == st["pwrfail"] == st["los"] == st["na"] == 0


# ---------------- STATE ----------------
last_state = None



# ---------------- UPDATE ENDPOINT ----------------
@app.route("/update", methods=["POST"])
def update():
    global last_state

    payload = request.get_json(force=True)
    regions_data = payload.get("data", {})

    new_raw = extract_state_from_regions(regions_data)
    new = {k: safe_int(v) for k, v in new_raw.items()}

    dump_debug_block("PRE_CHECK", regions_data, new_raw, new, last_state)

    if all_zero(new):
        dump_debug_block("ALL_ZERO_SKIP", regions_data, new_raw, new, last_state)
        log_system("⚠️ Received ALL ZERO state → skipped (SmartOLT glitch)")
        return jsonify({"status": "OK", "reason": "all_zero_skipped"})

    if last_state is None:
        dump_debug_block("FIRST_RUN", regions_data, new_raw, new, last_state)
        last_state = dict(new)

        title = "🟨 INITIAL VALUES"
        body = (
            f"Online: {new['online']}\n"
            f"Total Offline: {new['total']}\n"
            f"PwrFail: {new['pwrfail']}\n"
            f"LoS: {new['los']}\n"
            f"N/A: {new['na']}"
        )
        tg = (
            "*📡 Monitorimi Filloi*\n"
            f"🟢 Online: `{new['online']}`\n"
            f"🔴 Offline: `{new['total']}`\n"
            f"🔌 PwrFail: `{new['pwrfail']}`\n"
            f"📡 LoS: `{new['los']}`\n"
            f"❔ N/A: `{new['na']}`"
        )
        broadcast_event(title, body, tg)
        return jsonify({"status": "OK"})

    # DIFFS
    diff_on  = new["online"]  - last_state["online"]
    diff_tot = new["total"]   - last_state["total"]
    diff_pwr = new["pwrfail"] - last_state["pwrfail"]
    diff_los = new["los"]     - last_state["los"]
    diff_na  = new["na"]      - last_state["na"]

    diffs = {
        "online": diff_on,
        "total": diff_tot,
        "pwrfail": diff_pwr,
        "los": diff_los,
        "na": diff_na,
    }

    dump_debug_block("DIFF_EVAL", regions_data, new_raw, new, last_state, diffs)

    def br_details(st):
        return (
            f"🔌 PwrFail: {st['pwrfail']}\n"
            f"📡 LoS: {st['los']}\n"
            f"❔ N/A: {st['na']}"
        )

    # Offline UP + Online DOWN
    if diff_tot > 0 and diff_on < 0:
        title = "🚨 RRITJE E KLIENTËVE OFFLINE 🚨"
        body = (
            f"Offline: {last_state['total']} → {new['total']} (↑)\n"
            f"Online:  {last_state['online']} → {new['online']} (↓)\n\n"
            f"{br_details(new)}"
        )
        tg = (
            "🚨*RRITJE E KLIENTËVE OFFLINE*🚨\n"
            f"🔴Offline: {last_state['total']} → {new['total']}\n"
            f"🟢Online: {last_state['online']} → {new['online']}\n"
            "*DETAJE📜*\n"
            f"{br_details(new)}"
        )
        broadcast_event(title, body, tg)
        play_soft_alert()

    # Online UP + Offline DOWN
    elif diff_tot < 0 and diff_on > 0:
        title = "📡 LIDHJET U PËRMIRËSUAN"
        body = (
            f"Online: {last_state['online']} → {new['online']} (↑)\n"
            f"Offline: {last_state['total']} → {new['total']} (↓)\n\n"
            f"{br_details(new)}"
        )
        tg = (
            "📡 *LIDHJET U PËRMIRËSUAN*\n"
            f"🟢 {last_state['online']} → {new['online']}\n"
            f"🔴 {last_state['total']} → {new['total']}\n"
            "*DETAJE📜*\n"
            f"{br_details(new)}"
        )
        broadcast_event(title, body, tg)

    else:
        # Offline changed
        if diff_tot != 0:
            if diff_tot > 0:
                title = "❗ RRITJE E OFFLINE"
            else:
                title = "🌍 ULJE E OFFLINE"

            body = (
                f"Offline: {last_state['total']} → {new['total']}\n\n"
                f"{br_details(new)}"
            )
            tg = (
                f"{title}\n"
                f"{last_state['total']} → {new['total']}\n\n"
                f"{br_details(new)}"
            )
            broadcast_event(title, body, tg)
            if diff_tot > 0:
                play_soft_alert()

        # Online changed
        if diff_on != 0:
            if diff_on < 0:
                title = "🚨 ONLINE DROPPED"
            else:
                title = "💡 CONNECTIVITY RESTORED"

            body = (
                f"Online: {last_state['online']} → {new['online']}\n\n"
                f"{br_details(new)}"
            )
            tg = (
                f"{title}\n"
                f"{last_state['online']} → {new['online']}\n\n"
                f"{br_details(new)}"
            )
            broadcast_event(title, body, tg)
            if diff_on < 0:
                play_soft_alert()

    dump_debug_block("STATE_COMMIT", regions_data, new_raw, new, last_state, diffs)
    last_state = dict(new)

    return jsonify({"status": "OK"})


# ---------------- LOGS ENDPOINT ----------------
@app.route("/logs", methods=["GET"])
def logs():
    return jsonify({"notifications": notification_log, "system": system_log})


# ---------------- STATUS ENDPOINT ----------------
@app.route("/status", methods=["GET"])
def status():
    global last_state
    if last_state is None:
        return jsonify({"online":0,"total":0,"pwrfail":0,"los":0,"na":0})
    return jsonify(last_state)


# ---------------- MAIN ----------------
if __name__ == "__main__":
    print("🚀 Backend running at http://127.0.0.1:5005")
    print("🟢 Telegram:", "ENABLED" if TELEGRAM_ENABLED else "DISABLED")
    app.run(host="127.0.0.1", port=5005, debug=False)
