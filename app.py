from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import google.generativeai as genai
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI")

client_mongo = MongoClient(MONGO_URI)
db = client_mongo["rozgarbot"]
workers_col = db["workers"]
bookings_col = db["bookings"]
reviews_col = db["reviews"]

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-pro")

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
    user_message = request.json.get("message", "")
    user_name = request.json.get("user_name", "User")
    
    all_workers = list(workers_col.find({"available": True}, {"_id": 0}))
    workers_str = str(all_workers)
    
    prompt = f"""
Tu RozgarBot hai — ek AI agent jo India mein daily-wage workers (plumber, electrician, maid, driver, carpenter, cook) ko households se connect karta hai.

Available Workers Database (MongoDB se):
{workers_str}

User ka naam: {user_name}
User ka message: {user_message}

Tera kaam:
1. User ki zaroorat samjho (skill + area + date)
2. Database se best matching worker suggest karo
3. Agar user book karna chahta hai to booking confirm karo
4. Friendly Hinglish mein jawab do
5. Worker ka naam, skill, area, price aur rating clearly batao
6. Agar koi worker nahi mila to politely batao
"""
    
    response = model.generate_content(prompt)
    ai_reply = response.text
    
    booking_confirmed = False
    if any(word in user_message.lower() for word in ["book", "confirm", "chahiye", "bhejo", "send"]):
        for worker in all_workers:
            if worker["skill"].lower() in user_message.lower() or worker["area"].lower() in user_message.lower():
                create_booking(worker["name"], user_name, datetime.now().isoformat(), worker["skill"])
                booking_confirmed = True
                break
    
    return jsonify({
        "reply": ai_reply,
        "booking_confirmed": booking_confirmed
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
    return jsonify({"status": "RozgarBot API is running!", "version": "1.0"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
