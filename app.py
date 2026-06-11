from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import requests as http_requests
from datetime import datetime
import os
import json
import re

app = Flask(__name__)
CORS(app)

MONGO_URI = os.environ.get("MONGO_URI")
client_mongo = MongoClient(MONGO_URI)
db = client_mongo["rozgarbot"]
workers_col = db["workers"]
bookings_col = db["bookings"]

def call_ai(prompt):
    GROQ_KEY = os.environ.get("GROQ_API_KEY")
    if not GROQ_KEY:
        return json.dumps({"reply": "GROQ_API_KEY missing hai server pe.", "workers": [], "quick_replies": [], "booking_card": None})

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": "Bearer " + GROQ_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 1024
    }

    try:
        response = http_requests.post(url, json=payload, headers=headers, timeout=30)
        data = response.json()

        if "error" in data:
            err_msg = data["error"].get("message", "unknown error")
            return json.dumps({"reply": "AI Error: " + err_msg, "workers": [], "quick_replies": ["Dobara try karo"], "booking_card": None})

        if "choices" not in data or len(data["choices"]) == 0:
            return json.dumps({"reply": "Koi response nahi mila.", "workers": [], "quick_replies": [], "booking_card": None})

        return data["choices"][0]["message"]["content"]

    except Exception as e:
        return json.dumps({"reply": "Connection error: " + str(e), "workers": [], "quick_replies": ["Dobara try karo"], "booking_card": None})


def extract_json_from_text(text):
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        text = text[start:end+1]
    try:
        return json.loads(text)
    except Exception:
        return None


def create_booking(worker_name, user_name, date, skill):
    booking = {
        "worker_name": worker_name,
        "user_name": user_name,
        "date": date,
        "skill": skill,
        "status": "confirmed",
        "created_at": datetime.now().isoformat()
    }
    bookings_col.insert_one(booking)
    return booking


@app.route("/chat", methods=["POST"])
def chat():
    try:
        body = request.get_json(force=True)
        user_message = body.get("message", "")
        user_name = body.get("user_name", "User")

        all_workers = list(workers_col.find({"available": True}, {"_id": 0}))
        workers_str = json.dumps(all_workers, ensure_ascii=False)

        prompt = (
            "Tu RozgarBot hai — ek AI agent jo India mein daily-wage workers ko households se connect karta hai.\n\n"
            "Available Workers Database:\n" + workers_str + "\n\n"
            "User ka naam: " + user_name + "\n"
            "User ka message: \"" + user_message + "\"\n\n"
            "RULES:\n"
            "1. User ko HAMESHA \"" + user_name + "\" naam se address karo, kabhi Guest mat bolna\n"
            "2. Agar user saare/multiple workers maange toh SAARE matching workers return karo\n"
            "3. Hinglish mein jawab do\n"
            "4. STRICTLY sirf valid JSON return karo, koi extra text nahi\n\n"
            "EXACT JSON FORMAT:\n"
            "{\"reply\": \"message here\", \"workers\": [{\"name\": \"\", \"skill\": \"\", \"area\": \"\", \"price\": 0, \"rating\": 0.0, \"phone\": \"\"}], \"quick_replies\": [\"btn1\", \"btn2\"], \"booking_card\": null}\n\n"
            "workers = [] agar koi match nahi. booking_card = null always."
        )

        raw_reply = call_ai(prompt)
        parsed = extract_json_from_text(raw_reply)

        booking_confirmed = False

        if parsed:
            booking_words = ["book", "confirm", "chahiye", "bhejo", "send", "haan", "ok"]
            if any(word in user_message.lower() for word in booking_words):
                for worker in all_workers:
                    skill_match = worker.get("skill", "").lower() in user_message.lower()
                    area_match = worker.get("area", "").lower() in user_message.lower()
                    name_match = worker.get("name", "").lower() in user_message.lower()
                    if skill_match or area_match or name_match:
                        create_booking(worker["name"], user_name, datetime.now().isoformat(), worker["skill"])
                        booking_confirmed = True
                        parsed["booking_card"] = {
                            "worker": worker,
                            "status": "confirmed",
                            "message": worker["name"] + " aapko 30 min mein contact karenge. Booking confirmed!"
                        }
                        break

            return jsonify({
                "reply": parsed.get("reply", ""),
                "workers": parsed.get("workers", []),
                "quick_replies": parsed.get("quick_replies", []),
                "booking_card": parsed.get("booking_card", None),
                "booking_confirmed": booking_confirmed
            })
        else:
            return jsonify({
                "reply": raw_reply if raw_reply else "Dobara try karein.",
                "workers": [],
                "quick_replies": ["Plumber dhundho", "Electrician chahiye", "Maid book karo", "Driver bulao"],
                "booking_card": None,
                "booking_confirmed": False
            })

    except Exception as e:
        return jsonify({
            "reply": "Server error: " + str(e),
            "workers": [],
            "quick_replies": ["Dobara try karo"],
            "booking_card": None,
            "booking_confirmed": False
        }), 200


@app.route("/workers", methods=["GET"])
def get_workers():
    try:
        workers = list(workers_col.find({"available": True}, {"_id": 0}))
        return jsonify(workers)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/bookings", methods=["GET"])
def get_bookings():
    try:
        bookings = list(bookings_col.find({}, {"_id": 0}))
        return jsonify(bookings)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "RozgarBot API is running!", "version": "4.1"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
