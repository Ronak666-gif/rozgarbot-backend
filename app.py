from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import requests as http_requests
from datetime import datetime
import os
import json
import re
import uuid

app = Flask(__name__)
CORS(app)

MONGO_URI = os.environ.get("MONGO_URI")
client_mongo = MongoClient(MONGO_URI)
db = client_mongo["rozgarbot"]
workers_col = db["workers"]
bookings_col = db["bookings"]
reviews_col = db["reviews"]


# ─────────────────────────────────────────────
# AI CALL (Groq — Llama 3.1)
# ─────────────────────────────────────────────
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


# ─────────────────────────────────────────────
# JSON EXTRACTOR
# ─────────────────────────────────────────────
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


# ─────────────────────────────────────────────
# SMART MATCH SCORE (0-100)
# ─────────────────────────────────────────────
def calculate_match_score(worker, user_message):
    score = 50  # base
    msg = user_message.lower()

    # Skill match
    if worker.get("skill", "").lower() in msg:
        score += 30

    # Area match
    if worker.get("area", "").lower() in msg:
        score += 15

    # Rating boost
    rating = float(worker.get("rating", 0))
    if rating >= 4.5:
        score += 5
    elif rating >= 4.0:
        score += 3

    return min(score, 99)


# ─────────────────────────────────────────────
# BOOKING CREATOR
# ─────────────────────────────────────────────
def create_booking(worker_name, user_name, skill):
    booking_id = "RB" + str(uuid.uuid4())[:8].upper()
    booking = {
        "booking_id": booking_id,
        "worker_name": worker_name,
        "user_name": user_name,
        "skill": skill,
        "status": "confirmed",
        "created_at": datetime.now().isoformat()
    }
    bookings_col.insert_one(booking)
    return booking


# ─────────────────────────────────────────────
# SEED WORKERS (40+ workers across Jaipur)
# ─────────────────────────────────────────────
SEED_WORKERS = [
    # Jhotwara
    {"name": "Ramesh Kumar", "skill": "Plumber", "area": "Jhotwara", "price": 300, "rating": 4.5, "phone": "9876500001", "experience": "5 saal", "available": True},
    {"name": "Suresh Meena", "skill": "Electrician", "area": "Jhotwara", "price": 350, "rating": 4.7, "phone": "9876500002", "experience": "7 saal", "available": True},
    {"name": "Geeta Devi", "skill": "Maid", "area": "Jhotwara", "price": 200, "rating": 4.3, "phone": "9876500003", "experience": "3 saal", "available": True},
    {"name": "Mohan Lal", "skill": "Carpenter", "area": "Jhotwara", "price": 400, "rating": 4.6, "phone": "9876500004", "experience": "10 saal", "available": True},
    {"name": "Dinesh Driver", "skill": "Driver", "area": "Jhotwara", "price": 500, "rating": 4.4, "phone": "9876500005", "experience": "8 saal", "available": True},
    {"name": "Kavita Sharma", "skill": "Cook", "area": "Jhotwara", "price": 250, "rating": 4.8, "phone": "9876500006", "experience": "6 saal", "available": True},
    {"name": "Bhola Nath", "skill": "Painter", "area": "Jhotwara", "price": 450, "rating": 4.2, "phone": "9876500007", "experience": "4 saal", "available": True},
    {"name": "Raju Mistri", "skill": "Mason", "area": "Jhotwara", "price": 600, "rating": 4.5, "phone": "9876500008", "experience": "12 saal", "available": True},

    # Mansarovar
    {"name": "Vijay Singh", "skill": "Plumber", "area": "Mansarovar", "price": 320, "rating": 4.6, "phone": "9876500009", "experience": "6 saal", "available": True},
    {"name": "Anil Verma", "skill": "Electrician", "area": "Mansarovar", "price": 380, "rating": 4.5, "phone": "9876500010", "experience": "9 saal", "available": True},
    {"name": "Sunita Bai", "skill": "Maid", "area": "Mansarovar", "price": 220, "rating": 4.4, "phone": "9876500011", "experience": "5 saal", "available": True},
    {"name": "Harish Carpenter", "skill": "Carpenter", "area": "Mansarovar", "price": 420, "rating": 4.7, "phone": "9876500012", "experience": "8 saal", "available": True},
    {"name": "Santosh Driver", "skill": "Driver", "area": "Mansarovar", "price": 550, "rating": 4.3, "phone": "9876500013", "experience": "5 saal", "available": True},
    {"name": "Meena Cook", "skill": "Cook", "area": "Mansarovar", "price": 270, "rating": 4.9, "phone": "9876500014", "experience": "7 saal", "available": True},
    {"name": "Pramod Painter", "skill": "Painter", "area": "Mansarovar", "price": 430, "rating": 4.1, "phone": "9876500015", "experience": "3 saal", "available": True},
    {"name": "Kailash Nath", "skill": "AC Mechanic", "area": "Mansarovar", "price": 500, "rating": 4.6, "phone": "9876500016", "experience": "6 saal", "available": True},

    # Vaishali Nagar
    {"name": "Deepak Plumber", "skill": "Plumber", "area": "Vaishali Nagar", "price": 350, "rating": 4.7, "phone": "9876500017", "experience": "8 saal", "available": True},
    {"name": "Rakesh Electric", "skill": "Electrician", "area": "Vaishali Nagar", "price": 400, "rating": 4.8, "phone": "9876500018", "experience": "11 saal", "available": True},
    {"name": "Pushpa Devi", "skill": "Maid", "area": "Vaishali Nagar", "price": 240, "rating": 4.5, "phone": "9876500019", "experience": "4 saal", "available": True},
    {"name": "Nand Kishore", "skill": "Carpenter", "area": "Vaishali Nagar", "price": 450, "rating": 4.4, "phone": "9876500020", "experience": "9 saal", "available": True},
    {"name": "Ghanshyam Driver", "skill": "Driver", "area": "Vaishali Nagar", "price": 600, "rating": 4.6, "phone": "9876500021", "experience": "10 saal", "available": True},
    {"name": "Sushila Cook", "skill": "Cook", "area": "Vaishali Nagar", "price": 300, "rating": 4.7, "phone": "9876500022", "experience": "8 saal", "available": True},
    {"name": "Mahesh Painter", "skill": "Painter", "area": "Vaishali Nagar", "price": 480, "rating": 4.3, "phone": "9876500023", "experience": "5 saal", "available": True},
    {"name": "Sunil AC", "skill": "AC Mechanic", "area": "Vaishali Nagar", "price": 550, "rating": 4.8, "phone": "9876500024", "experience": "7 saal", "available": True},

    # Malviya Nagar
    {"name": "Prakash Plumber", "skill": "Plumber", "area": "Malviya Nagar", "price": 330, "rating": 4.4, "phone": "9876500025", "experience": "5 saal", "available": True},
    {"name": "Umesh Electric", "skill": "Electrician", "area": "Malviya Nagar", "price": 370, "rating": 4.6, "phone": "9876500026", "experience": "8 saal", "available": True},
    {"name": "Laxmi Bai", "skill": "Maid", "area": "Malviya Nagar", "price": 230, "rating": 4.2, "phone": "9876500027", "experience": "3 saal", "available": True},
    {"name": "Gopal Carpenter", "skill": "Carpenter", "area": "Malviya Nagar", "price": 410, "rating": 4.5, "phone": "9876500028", "experience": "7 saal", "available": True},
    {"name": "Ramji Cook", "skill": "Cook", "area": "Malviya Nagar", "price": 260, "rating": 4.6, "phone": "9876500029", "experience": "6 saal", "available": True},
    {"name": "Babu Painter", "skill": "Painter", "area": "Malviya Nagar", "price": 440, "rating": 4.4, "phone": "9876500030", "experience": "4 saal", "available": True},

    # Sanganer
    {"name": "Manoj Plumber", "skill": "Plumber", "area": "Sanganer", "price": 290, "rating": 4.3, "phone": "9876500031", "experience": "4 saal", "available": True},
    {"name": "Pappu Electric", "skill": "Electrician", "area": "Sanganer", "price": 340, "rating": 4.5, "phone": "9876500032", "experience": "6 saal", "available": True},
    {"name": "Champa Devi", "skill": "Maid", "area": "Sanganer", "price": 190, "rating": 4.1, "phone": "9876500033", "experience": "2 saal", "available": True},
    {"name": "Shyam Driver", "skill": "Driver", "area": "Sanganer", "price": 480, "rating": 4.4, "phone": "9876500034", "experience": "7 saal", "available": True},
    {"name": "Heera Cook", "skill": "Cook", "area": "Sanganer", "price": 240, "rating": 4.5, "phone": "9876500035", "experience": "5 saal", "available": True},

    # Jagatpura
    {"name": "Lalit Plumber", "skill": "Plumber", "area": "Jagatpura", "price": 310, "rating": 4.4, "phone": "9876500036", "experience": "5 saal", "available": True},
    {"name": "Bharat Electric", "skill": "Electrician", "area": "Jagatpura", "price": 360, "rating": 4.7, "phone": "9876500037", "experience": "9 saal", "available": True},
    {"name": "Sarla Maid", "skill": "Maid", "area": "Jagatpura", "price": 210, "rating": 4.3, "phone": "9876500038", "experience": "3 saal", "available": True},
    {"name": "Naresh Carpenter", "skill": "Carpenter", "area": "Jagatpura", "price": 430, "rating": 4.6, "phone": "9876500039", "experience": "8 saal", "available": True},
    {"name": "Jitendra AC", "skill": "AC Mechanic", "area": "Jagatpura", "price": 520, "rating": 4.5, "phone": "9876500040", "experience": "6 saal", "available": True},
]


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "RozgarBot API is running!", "version": "5.0"})


@app.route("/ping", methods=["GET"])
def ping():
    """Keep-alive endpoint to prevent Render cold start"""
    return jsonify({"status": "alive", "time": datetime.now().isoformat()})


@app.route("/seed-workers", methods=["POST"])
def seed_workers():
    """Seed 40+ workers into MongoDB — call once"""
    try:
        workers_col.delete_many({})
        workers_col.insert_many(SEED_WORKERS)
        return jsonify({"message": f"{len(SEED_WORKERS)} workers seeded successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/chat", methods=["POST"])
def chat():
    try:
        body = request.get_json(force=True)
        user_message = body.get("message", "").strip()
        user_name = body.get("user_name", "").strip()

        # Fallback if name empty
        if not user_name:
            user_name = "Dost"

        # Input validation
        if not user_message:
            return jsonify({
                "reply": "Kuch toh bolo! Kya chahiye aapko?",
                "workers": [],
                "quick_replies": ["Plumber dhundho", "Electrician chahiye", "Maid book karo", "Driver bulao"],
                "booking_card": None,
                "booking_confirmed": False
            })

        if len(user_message) < 2 or not re.search(r'[a-zA-Z\u0900-\u097F]', user_message):
            return jsonify({
                "reply": f"{user_name}, please clearly batao — kaunsa kaam chahiye aur kaunse area mein?",
                "workers": [],
                "quick_replies": ["Plumber dhundho", "Electrician chahiye", "Maid book karo", "Driver bulao"],
                "booking_card": None,
                "booking_confirmed": False
            })

        all_workers = list(workers_col.find({"available": True}, {"_id": 0}))
        workers_str = json.dumps(all_workers, ensure_ascii=False)

        prompt = (
            "Tu RozgarBot hai — India mein daily-wage workers ko households se connect karne wala AI agent.\n\n"
            "Available Workers Database:\n" + workers_str + "\n\n"
            "User ka naam: " + user_name + "\n"
            "User ka message: \"" + user_message + "\"\n\n"
            "RULES:\n"
            "1. User ko HAMESHA \"" + user_name + "\" naam se address karo — kabhi 'Guest' ya 'User' mat bolna\n"
            "2. Agar user saare/multiple workers maange ya koi specific skill maange toh SAARE matching workers return karo\n"
            "3. Hinglish mein jawab do — friendly aur helpful tone rakho\n"
            "4. Agar koi bhi worker match nahi karta toh workers = [] return karo aur suggest karo ki kya search karein\n"
            "5. STRICTLY sirf valid JSON return karo, koi extra text nahi\n\n"
            "EXACT JSON FORMAT (koi bhi field miss mat karo):\n"
            "{\"reply\": \"message here\", \"workers\": [{\"name\": \"\", \"skill\": \"\", \"area\": \"\", \"price\": 0, \"rating\": 0.0, \"phone\": \"\", \"experience\": \"\"}], \"quick_replies\": [\"btn1\", \"btn2\", \"btn3\"], \"booking_card\": null}\n\n"
            "workers = [] agar koi match nahi. booking_card = null always (backend handle karega)."
        )

        raw_reply = call_ai(prompt)
        parsed = extract_json_from_text(raw_reply)

        booking_confirmed = False

        if parsed:
            # Add match score to each worker
            workers_with_score = []
            for w in parsed.get("workers", []):
                w["match_score"] = calculate_match_score(w, user_message)
                workers_with_score.append(w)

            # Sort by match score descending
            workers_with_score.sort(key=lambda x: x.get("match_score", 0), reverse=True)

            # Booking detection
            booking_words = ["book", "confirm", "chahiye", "bhejo", "send", "haan", "ok", "theek", "karwa do", "bulao"]
            if any(word in user_message.lower() for word in booking_words):
                for worker in all_workers:
                    skill_match = worker.get("skill", "").lower() in user_message.lower()
                    area_match = worker.get("area", "").lower() in user_message.lower()
                    name_match = worker.get("name", "").lower() in user_message.lower()
                    if skill_match or area_match or name_match:
                        booking = create_booking(worker["name"], user_name, worker["skill"])
                        booking_confirmed = True
                        parsed["booking_card"] = {
                            "worker": worker,
                            "status": "confirmed",
                            "booking_id": booking["booking_id"],
                            "message": f"{worker['name']} aapko 30 min mein contact karenge. Booking confirmed!"
                        }
                        break

            return jsonify({
                "reply": parsed.get("reply", ""),
                "workers": workers_with_score,
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
            "reply": "Server mein thodi problem aayi. Ek minute baad dobara try karein.",
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
        user_name = request.args.get("user_name", "")
        query = {}
        if user_name:
            query["user_name"] = {"$regex": user_name, "$options": "i"}
        bookings = list(bookings_col.find(query, {"_id": 0}))
        return jsonify(bookings)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/cancel-booking", methods=["POST"])
def cancel_booking():
    try:
        body = request.get_json(force=True)
        booking_id = body.get("booking_id", "")
        if not booking_id:
            return jsonify({"error": "booking_id required"}), 400
        result = bookings_col.update_one(
            {"booking_id": booking_id},
            {"$set": {"status": "cancelled", "cancelled_at": datetime.now().isoformat()}}
        )
        if result.matched_count == 0:
            return jsonify({"error": "Booking nahi mili"}), 404
        return jsonify({"message": "Booking cancel ho gayi!", "booking_id": booking_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/rate-worker", methods=["POST"])
def rate_worker():
    try:
        body = request.get_json(force=True)
        worker_name = body.get("worker_name", "")
        user_name = body.get("user_name", "")
        rating = body.get("rating", 0)
        review_text = body.get("review", "")

        if not worker_name or not rating:
            return jsonify({"error": "worker_name aur rating required hai"}), 400

        review = {
            "worker_name": worker_name,
            "user_name": user_name,
            "rating": float(rating),
            "review": review_text,
            "created_at": datetime.now().isoformat()
        }
        reviews_col.insert_one(review)

        # Update worker avg rating
        all_reviews = list(reviews_col.find({"worker_name": worker_name}, {"_id": 0}))
        if all_reviews:
            avg = sum(r["rating"] for r in all_reviews) / len(all_reviews)
            workers_col.update_one(
                {"name": worker_name},
                {"$set": {"rating": round(avg, 1)}}
            )

        return jsonify({"message": "Rating submit ho gayi! Shukriya.", "new_avg": round(avg, 1) if all_reviews else rating})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/stats", methods=["GET"])
def get_stats():
    """Admin dashboard stats"""
    try:
        total_workers = workers_col.count_documents({"available": True})
        total_bookings = bookings_col.count_documents({})
        confirmed_bookings = bookings_col.count_documents({"status": "confirmed"})
        cancelled_bookings = bookings_col.count_documents({"status": "cancelled"})

        # Popular skills
        pipeline = [
            {"$group": {"_id": "$skill", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        popular_skills = list(bookings_col.aggregate(pipeline))

        # Area wise demand
        area_pipeline = [
            {"$group": {"_id": "$area", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        area_demand = list(workers_col.aggregate(area_pipeline))

        return jsonify({
            "total_workers": total_workers,
            "total_bookings": total_bookings,
            "confirmed_bookings": confirmed_bookings,
            "cancelled_bookings": cancelled_bookings,
            "popular_skills": popular_skills,
            "area_demand": area_demand
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
