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
        return '{"reply": "API key missing hai server pe.", "workers": [], "quick_replies": [], "booking_card": null}'
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 1024
    }
    
    response = http_requests.post(url, json=payload, headers=headers, timeout=30)
    data = response.json()
    
    # Handle Groq errors properly
    if "error" in data:
        return f'{{"reply": "AI Error: {data[\"error\"].get(\"message\", \"unknown\")}", "workers": [], "quick_replies": ["Dobara try karo"], "booking_card": null}}'
    
    if "choices" not in data or len(data["choices"]) == 0:
        return f'{{"reply": "Koi response nahi mila: {str(data)[:100]}", "workers": [], "quick_replies": [], "booking_card": null}}'
    
    return data["choices"][0]["message"]["content"]

def extract_json_from_text(text):
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
    # Find first { to last } in case there's extra text
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

        prompt = f"""Tu RozgarBot hai — ek AI agent jo India mein daily-wage workers ko households se connect karta hai.

Available Workers Database:
{workers_str}

User ka naam: {user_name}
User ka message: "{user_message}"

RULES:
1. User ko HAMESHA "{user_name}" naam se address karo, kabhi "Guest" mat bolna
2. Agar user saare/multiple workers maange toh SAARE matching workers return karo, sirf ek nahi
3. Hinglish mein jawab do
4. STRICTLY sirf valid JSON return karo — koi extra text, explanation, ya markdown nahi

JSON FORMAT (exactly this structure):
{{"reply": "message here using name {user_name}", "workers": [{{"name": "", "skill": "", "area": "", "price": 0, "rating": 0.0, "phone": ""}}], "quick_replies": ["btn1", "btn2", "btn3"], "booking_card": null}}

workers = empty array [] agar koi match nahi. booking_card = null always unless booking confirmed."""

        raw_reply = call_ai(prompt)
        parsed = extract_json_from_text(raw_reply)

        booking_confirmed = False

        if parsed:
            if any(word in user_message.lower() for word in ["book", "confirm", "chahiye", "bhejo", "send", "haan", "ok"]):
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
                            "message": f"Booking confirmed! {worker['name']} aapko 30 min mein contact karenge."
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
            "reply": f"Server error: {str(e)}",
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
    return jsonify({"status": "RozgarBot API is running!", "version": "4.0"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
