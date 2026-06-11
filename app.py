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

def call_gemini(prompt):
    url = "https://freemodel.dev/v1/chat/completions"
    headers = {
        "Authorization": "Bearer fe_oa_a8c933b6689a9f89d1f9ff778d4a17e64c864a4ab502e54e",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}]
    }
    response = http_requests.post(url, json=payload, headers=headers)
    data = response.json()
    try:
        return data["choices"][0]["message"]["content"]
    except:
        return f"Error: {str(data)}"

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

def extract_json_from_text(text):
    """Extract JSON from Gemini response which may have markdown code blocks"""
    # Remove markdown code blocks if present
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
    try:
        return json.loads(text)
    except:
        return None

@app.route("/chat", methods=["POST"])
def chat():
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
2. Agar user multiple workers maange (jaise "saare plumber", "all electricians", "kitne available hain") toh database se SAARE matching workers return karo — sirf ek nahi
3. Hinglish mein jawab do (Hindi + English mix)
4. Agar booking confirm ho toh booking_card bhi bhejo

RESPONSE FORMAT — ONLY valid JSON return karo, kuch aur nahi:
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
  "quick_replies": ["relevant button 1", "relevant button 2", "relevant button 3"],
  "booking_card": null
}}

- "workers" array mein SAARE matching workers dalo (empty array [] agar koi nahi mila)
- "booking_card" null rakho jab tak booking confirm na ho
- Sirf JSON return karo, koi extra text nahi"""

    raw_reply = call_gemini(prompt)
    parsed = extract_json_from_text(raw_reply)

    booking_confirmed = False

    if parsed:
        # Check if booking should be triggered
        if any(word in user_message.lower() for word in ["book", "confirm", "chahiye", "bhejo", "send", "haan", "ok"]):
            for worker in all_workers:
                if worker.get("skill", "").lower() in user_message.lower() or \
                   worker.get("area", "").lower() in user_message.lower() or \
                   worker.get("name", "").lower() in user_message.lower():
                    booking = create_booking(worker["name"], user_name, datetime.now().isoformat(), worker["skill"])
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
            "reply": raw_reply,
            "workers": [],
            "quick_replies": ["Plumber dhundho", "Electrician chahiye", "Maid book karo"],
            "booking_card": None,
            "booking_confirmed": False
        })

@app.route("/workers", methods=["GET"])
def get_workers():
    workers = list(workers_col.find({"available": True}, {"_id": 0}))
    return jsonify(workers)

@app.route("/bookings", methods=["GET"])
def get_bookings():
    bookings = list(bookings_col.find({}, {"_id": 0}))
    return jsonify(bookings)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "RozgarBot API is running!", "version": "2.0"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
