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

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI")

client_mongo = MongoClient(MONGO_URI)
db = client_mongo["rozgarbot"]
workers_col = db["workers"]
bookings_col = db["bookings"]
reviews_col = db["reviews"]

def call_ai(prompt):
    GROQ_KEY = os.environ.get("GROQ_API_KEY")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        response = http_requests.post(url, json=payload, headers=headers, timeout=30)
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Connection error: {str(e)}"

def extract_json_from_text(text):
    """Extract JSON from AI response which may have markdown code blocks"""
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
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
        user_message = request.json.get("message", "")
        user_name = request.json.get("user_name", "User")

        all_workers = list(workers_col.find({"available": True}, {"_id": 0}))
        workers_str = json.dumps(all_workers, ensure_ascii=False)

        prompt = f"""Tu RozgarBot hai — ek AI agent jo India mein daily-wage workers (plumber, electrician, maid, driver, carpenter, cook) ko households se connect karta hai.

Available Workers Database:
{workers_str}

User ka naam: {user_name}
User ka message: "{user_message}"

IMPORTANT RULES:
1. User ko HAMESHA unke naam "{user_name}" se address karo, kabhi "Guest" mat bolna
2. Agar user multiple workers maange toh database se SAARE matching workers return karo
3. Hinglish mein jawab do (Hindi + English mix)
4. ONLY valid JSON return karo, kuch aur nahi, no markdown, no extra text

RESPONSE FORMAT (strict JSON only):
{{
  "reply": "User se baat karne wala message {user_name} ka naam use karke",
  "workers": [
    {{
      "name": "worker name",
      "skill": "skill",
      "area": "area",
      "price": 300,
      "rating": 4.5,
      "phone": "phone number"
    }}
  ],
  "quick_replies": ["Button 1", "Button 2", "Button 3"],
  "booking_card": null
}}

- workers array mein SAARE matching workers dalo (empty array [] agar koi nahi mila)
- booking_card null rakho jab tak booking confirm na ho
- STRICTLY only JSON, no extra explanation"""

        raw_reply = call_ai(prompt)
        parsed = extract_json_from_text(raw_reply)

        booking_confirmed = False

        if parsed:
            if any(word in user_message.lower() for word in ["book", "confirm", "chahiye", "bhejo", "send", "haan", "ok"]):
                for worker in all_workers:
                    if worker.get("skill", "").lower() in user_message.lower() or \
                       worker.get("area", "").lower() in user_message.lower() or \
                       worker.get("name", "").lower() in user_message.lower():
                        create_booking(worker["name"], user_name, datetime.now().isoformat(), worker["skill"])
                        booking_confirmed = True
                        parsed["booking_card"] = {
                            "worker": worker,
                            "status": "confirmed",
                            "message": f"Booking confirmed! {worker['name']} aapko jald hi contact karenge."
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
            # Fallback if JSON parsing fails
            return jsonify({
                "reply": raw_reply if raw_reply else "Kuch problem ho gayi, dobara try karein.",
                "workers": [],
                "quick_replies": ["Plumber dhundho", "Electrician chahiye", "Maid book karo"],
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
        }), 200  # Return 200 so frontend doesn't show connection error

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
    return jsonify({"status": "RozgarBot API is running!", "version": "3.0"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
