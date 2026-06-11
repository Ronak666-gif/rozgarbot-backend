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
        return json.dumps({"reply": "GROQ_API_KEY missing on server.", "workers": [], "quick_replies": [], "booking_card": None})

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
            return json.dumps({"reply": "AI Error: " + err_msg, "workers": [], "quick_replies": ["Try again"], "booking_card": None})

        if "choices" not in data or len(data["choices"]) == 0:
            return json.dumps({"reply": "No response received.", "workers": [], "quick_replies": [], "booking_card": None})

        return data["choices"][0]["message"]["content"]

    except Exception as e:
        return json.dumps({"reply": "Connection error: " + str(e), "workers": [], "quick_replies": ["Try again"], "booking_card": None})


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
# SMART MATCH SCORE (0-99)
# ─────────────────────────────────────────────
def calculate_match_score(worker, user_message):
    score = 50
    msg = user_message.lower()

    if worker.get("skill", "").lower() in msg:
        score += 30
    if worker.get("area", "").lower() in msg:
        score += 10
    if worker.get("city", "").lower() in msg:
        score += 5
    if worker.get("country", "").lower() in msg:
        score += 3

    rating = float(worker.get("rating", 0))
    if rating >= 4.8:
        score += 6
    elif rating >= 4.5:
        score += 4
    elif rating >= 4.0:
        score += 2

    return min(score, 99)


# ─────────────────────────────────────────────
# BOOKING CREATOR
# ─────────────────────────────────────────────
def create_booking(worker, user_name):
    booking_id = "RB-" + str(uuid.uuid4())[:8].upper()
    booking = {
        "booking_id": booking_id,
        "worker_name": worker.get("name"),
        "worker_skill": worker.get("skill"),
        "worker_area": worker.get("area"),
        "worker_city": worker.get("city"),
        "worker_country": worker.get("country"),
        "worker_phone": worker.get("phone"),
        "user_name": user_name,
        "status": "confirmed",
        "created_at": datetime.now().isoformat()
    }
    bookings_col.insert_one(booking)
    return booking


# ─────────────────────────────────────────────
# SEED DATA — 200+ Workers, Global
# ─────────────────────────────────────────────
def generate_workers():
    workers = []

    # ── INDIA ──────────────────────────────────

    # Jaipur, Rajasthan
    jaipur_workers = [
        ("Ramesh Kumar", "Plumber", "Jhotwara", 300, 4.5, "9876500001", "5 years"),
        ("Suresh Meena", "Electrician", "Jhotwara", 350, 4.7, "9876500002", "7 years"),
        ("Geeta Devi", "Maid", "Jhotwara", 200, 4.3, "9876500003", "3 years"),
        ("Mohan Lal", "Carpenter", "Jhotwara", 400, 4.6, "9876500004", "10 years"),
        ("Dinesh Saini", "Driver", "Jhotwara", 500, 4.4, "9876500005", "8 years"),
        ("Kavita Sharma", "Cook", "Jhotwara", 250, 4.8, "9876500006", "6 years"),
        ("Bhola Nath", "Painter", "Jhotwara", 450, 4.2, "9876500007", "4 years"),
        ("Raju Mistri", "Mason", "Jhotwara", 600, 4.5, "9876500008", "12 years"),
        ("Vijay Singh", "Plumber", "Mansarovar", 320, 4.6, "9876500009", "6 years"),
        ("Anil Verma", "Electrician", "Mansarovar", 380, 4.5, "9876500010", "9 years"),
        ("Sunita Bai", "Maid", "Mansarovar", 220, 4.4, "9876500011", "5 years"),
        ("Harish Sharma", "Carpenter", "Mansarovar", 420, 4.7, "9876500012", "8 years"),
        ("Santosh Driver", "Driver", "Mansarovar", 550, 4.3, "9876500013", "5 years"),
        ("Meena Devi", "Cook", "Mansarovar", 270, 4.9, "9876500014", "7 years"),
        ("Kailash Nath", "AC Mechanic", "Mansarovar", 500, 4.6, "9876500016", "6 years"),
        ("Deepak Sharma", "Plumber", "Vaishali Nagar", 350, 4.7, "9876500017", "8 years"),
        ("Rakesh Verma", "Electrician", "Vaishali Nagar", 400, 4.8, "9876500018", "11 years"),
        ("Pushpa Devi", "Maid", "Vaishali Nagar", 240, 4.5, "9876500019", "4 years"),
        ("Nand Kishore", "Carpenter", "Vaishali Nagar", 450, 4.4, "9876500020", "9 years"),
        ("Ghanshyam Das", "Driver", "Vaishali Nagar", 600, 4.6, "9876500021", "10 years"),
        ("Sunil Kumar", "AC Mechanic", "Vaishali Nagar", 550, 4.8, "9876500024", "7 years"),
        ("Prakash Mali", "Gardener", "Malviya Nagar", 280, 4.5, "9876500025", "5 years"),
        ("Umesh Gupta", "Electrician", "Malviya Nagar", 370, 4.6, "9876500026", "8 years"),
        ("Laxmi Bai", "Maid", "Malviya Nagar", 230, 4.2, "9876500027", "3 years"),
        ("Gopal Sharma", "Carpenter", "Malviya Nagar", 410, 4.5, "9876500028", "7 years"),
        ("Manoj Kumar", "Plumber", "Sanganer", 290, 4.3, "9876500031", "4 years"),
        ("Shyam Lal", "Driver", "Sanganer", 480, 4.4, "9876500034", "7 years"),
        ("Lalit Sharma", "Plumber", "Jagatpura", 310, 4.4, "9876500036", "5 years"),
        ("Bharat Singh", "Electrician", "Jagatpura", 360, 4.7, "9876500037", "9 years"),
        ("Jitendra Kumar", "AC Mechanic", "Jagatpura", 520, 4.5, "9876500040", "6 years"),
        ("Priya Kumari", "Babysitter", "Vaishali Nagar", 300, 4.6, "9876500041", "3 years"),
        ("Rajesh Tailor", "Tailor", "Jhotwara", 350, 4.4, "9876500042", "8 years"),
        ("Mukesh Sharma", "Pest Control", "Mansarovar", 600, 4.7, "9876500043", "6 years"),
        ("Sanjay Gupta", "CCTV Technician", "Vaishali Nagar", 700, 4.5, "9876500044", "5 years"),
        ("Arjun Meena", "Solar Technician", "Malviya Nagar", 800, 4.8, "9876500045", "4 years"),
    ]
    for w in jaipur_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "Jaipur", "state": "Rajasthan", "country": "India", "price": w[3], "price_currency": "INR", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    # Delhi
    delhi_workers = [
        ("Amit Sharma", "Plumber", "Dwarka", 400, 4.6, "9811000001", "6 years"),
        ("Rohit Verma", "Electrician", "Saket", 450, 4.8, "9811000002", "10 years"),
        ("Seema Devi", "Maid", "Lajpat Nagar", 300, 4.4, "9811000003", "5 years"),
        ("Vinod Kumar", "Driver", "Rohini", 700, 4.5, "9811000004", "12 years"),
        ("Sunita Rani", "Cook", "Karol Bagh", 350, 4.7, "9811000005", "7 years"),
        ("Ravi Sharma", "Carpenter", "Janakpuri", 550, 4.6, "9811000006", "9 years"),
        ("Pooja Devi", "Babysitter", "Vasant Kunj", 400, 4.9, "9811000007", "4 years"),
        ("Naresh Kumar", "AC Mechanic", "Pitampura", 650, 4.7, "9811000008", "8 years"),
        ("Deepak Singh", "Security Guard", "Noida Sector 18", 600, 4.3, "9811000009", "6 years"),
        ("Anita Sharma", "Caretaker/Nurse", "South Extension", 500, 4.8, "9811000010", "5 years"),
        ("Suresh Pal", "Painter", "Uttam Nagar", 500, 4.4, "9811000011", "6 years"),
        ("Harendra Singh", "Mason", "Shahdara", 700, 4.5, "9811000012", "15 years"),
        ("Meena Kumari", "Washer/Laundry", "Mayur Vihar", 250, 4.2, "9811000013", "4 years"),
        ("Pankaj Kumar", "Gardener", "Greater Kailash", 350, 4.6, "9811000014", "5 years"),
        ("Vikram Singh", "Welder", "Wazirpur", 600, 4.5, "9811000015", "10 years"),
    ]
    for w in delhi_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "Delhi", "state": "Delhi", "country": "India", "price": w[3], "price_currency": "INR", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    # Mumbai
    mumbai_workers = [
        ("Santosh Patil", "Plumber", "Andheri", 500, 4.7, "9922000001", "8 years"),
        ("Pradeep Sawant", "Electrician", "Bandra", 550, 4.8, "9922000002", "11 years"),
        ("Rekha Nair", "Maid", "Powai", 400, 4.5, "9922000003", "6 years"),
        ("Ramesh Jadhav", "Driver", "Thane", 800, 4.6, "9922000004", "14 years"),
        ("Lata Pawar", "Cook", "Borivali", 450, 4.9, "9922000005", "8 years"),
        ("Ganesh More", "Carpenter", "Kurla", 650, 4.5, "9922000006", "10 years"),
        ("Surekha Desai", "Caretaker/Nurse", "Juhu", 600, 4.8, "9922000007", "7 years"),
        ("Arun Bhosale", "AC Mechanic", "Malad", 750, 4.6, "9922000008", "9 years"),
        ("Sushma Yadav", "Babysitter", "Chembur", 500, 4.7, "9922000009", "5 years"),
        ("Prakash Kamble", "Security Guard", "Navi Mumbai", 700, 4.4, "9922000010", "8 years"),
        ("Vijay Shinde", "Painter", "Dadar", 600, 4.3, "9922000011", "7 years"),
        ("Sunil Gaikwad", "Pest Control", "Kalyan", 800, 4.6, "9922000012", "6 years"),
        ("Mohan Tiwari", "Tailor", "Dharavi", 400, 4.5, "9922000013", "12 years"),
        ("Kavita Rane", "Tutor", "Mulund", 700, 4.9, "9922000014", "5 years"),
    ]
    for w in mumbai_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "Mumbai", "state": "Maharashtra", "country": "India", "price": w[3], "price_currency": "INR", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    # Bangalore
    bangalore_workers = [
        ("Suresh Reddy", "Plumber", "Koramangala", 450, 4.6, "9845000001", "7 years"),
        ("Ravi Kumar", "Electrician", "Whitefield", 500, 4.8, "9845000002", "10 years"),
        ("Lakshmi Devi", "Maid", "Indiranagar", 350, 4.5, "9845000003", "5 years"),
        ("Manjunath S", "Driver", "HSR Layout", 750, 4.7, "9845000004", "11 years"),
        ("Geetha Rao", "Cook", "Jayanagar", 400, 4.9, "9845000005", "8 years"),
        ("Venkatesh B", "Carpenter", "BTM Layout", 600, 4.6, "9845000006", "9 years"),
        ("Priya Nair", "Babysitter", "Marathahalli", 450, 4.8, "9845000007", "4 years"),
        ("Kiran Kumar", "AC Mechanic", "Electronic City", 700, 4.7, "9845000008", "8 years"),
        ("Ramesh Gowda", "Gardener", "Sadashivanagar", 350, 4.5, "9845000009", "6 years"),
        ("Anand Raj", "CCTV Technician", "Bannerghatta Road", 800, 4.6, "9845000010", "5 years"),
        ("Shobha Kumari", "Caretaker/Nurse", "JP Nagar", 550, 4.8, "9845000011", "7 years"),
        ("Nagesh Rao", "Solar Technician", "Yelahanka", 900, 4.7, "9845000012", "4 years"),
    ]
    for w in bangalore_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "Bangalore", "state": "Karnataka", "country": "India", "price": w[3], "price_currency": "INR", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    # Chennai
    chennai_workers = [
        ("Murugan K", "Plumber", "Anna Nagar", 400, 4.5, "9444000001", "6 years"),
        ("Selvam R", "Electrician", "T Nagar", 450, 4.7, "9444000002", "9 years"),
        ("Meenakshi S", "Maid", "Adyar", 300, 4.4, "9444000003", "4 years"),
        ("Rajan P", "Driver", "Velachery", 700, 4.6, "9444000004", "13 years"),
        ("Saranya D", "Cook", "Guindy", 380, 4.8, "9444000005", "7 years"),
        ("Kannan V", "Mason", "Tambaram", 650, 4.5, "9444000006", "11 years"),
        ("Priya M", "Tutor", "Nungambakkam", 600, 4.9, "9444000007", "5 years"),
        ("Arumugam T", "Welder", "Ambattur", 550, 4.4, "9444000008", "8 years"),
    ]
    for w in chennai_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "Chennai", "state": "Tamil Nadu", "country": "India", "price": w[3], "price_currency": "INR", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    # Hyderabad
    hyderabad_workers = [
        ("Venkat Rao", "Plumber", "Hitech City", 420, 4.6, "9848000001", "7 years"),
        ("Srikanth M", "Electrician", "Gachibowli", 480, 4.8, "9848000002", "10 years"),
        ("Padmavathi D", "Maid", "Jubilee Hills", 320, 4.5, "9848000003", "5 years"),
        ("Ramu K", "Driver", "Secunderabad", 720, 4.5, "9848000004", "12 years"),
        ("Lakshmi B", "Cook", "Begumpet", 400, 4.7, "9848000005", "8 years"),
        ("Suresh Naidu", "AC Mechanic", "LB Nagar", 680, 4.6, "9848000006", "7 years"),
        ("Anitha Reddy", "Caretaker/Nurse", "Banjara Hills", 580, 4.9, "9848000007", "6 years"),
        ("Mahesh T", "Pest Control", "Miyapur", 750, 4.5, "9848000008", "5 years"),
    ]
    for w in hyderabad_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "Hyderabad", "state": "Telangana", "country": "India", "price": w[3], "price_currency": "INR", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    # Pune
    pune_workers = [
        ("Sandip Jagtap", "Plumber", "Kothrud", 380, 4.5, "9823000001", "6 years"),
        ("Nilesh Mane", "Electrician", "Viman Nagar", 430, 4.7, "9823000002", "8 years"),
        ("Sunanda Kulkarni", "Maid", "Aundh", 280, 4.4, "9823000003", "4 years"),
        ("Sachin Pawar", "Driver", "Hinjewadi", 680, 4.6, "9823000004", "10 years"),
        ("Archana Bhosle", "Cook", "Shivajinagar", 380, 4.8, "9823000005", "7 years"),
        ("Rahul Deshmukh", "Gym Trainer", "Baner", 700, 4.9, "9823000006", "5 years"),
        ("Priti Shelar", "Babysitter", "Wakad", 420, 4.7, "9823000007", "3 years"),
    ]
    for w in pune_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "Pune", "state": "Maharashtra", "country": "India", "price": w[3], "price_currency": "INR", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    # Kolkata
    kolkata_workers = [
        ("Subhash Das", "Plumber", "Salt Lake", 350, 4.4, "9831000001", "5 years"),
        ("Tapas Ghosh", "Electrician", "Park Street", 400, 4.6, "9831000002", "8 years"),
        ("Mamata Roy", "Maid", "Ballygunge", 250, 4.3, "9831000003", "4 years"),
        ("Ratan Mondal", "Driver", "Howrah", 650, 4.5, "9831000004", "11 years"),
        ("Chhaya Biswas", "Cook", "New Town", 350, 4.7, "9831000005", "7 years"),
        ("Kartik Pal", "Mason", "Dum Dum", 600, 4.4, "9831000006", "10 years"),
        ("Ananya Sen", "Tutor", "Jadavpur", 550, 4.9, "9831000007", "5 years"),
    ]
    for w in kolkata_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "Kolkata", "state": "West Bengal", "country": "India", "price": w[3], "price_currency": "INR", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    # Ahmedabad
    ahmedabad_workers = [
        ("Bhavesh Patel", "Plumber", "Satellite", 360, 4.5, "9979000001", "6 years"),
        ("Jignesh Shah", "Electrician", "Navrangpura", 410, 4.7, "9979000002", "9 years"),
        ("Hetal Parmar", "Maid", "Vastrapur", 270, 4.4, "9979000003", "4 years"),
        ("Kiran Desai", "Driver", "Bopal", 640, 4.5, "9979000004", "10 years"),
        ("Sonal Mehta", "Cook", "Prahlad Nagar", 370, 4.8, "9979000005", "7 years"),
        ("Deepak Thakkar", "AC Mechanic", "Gota", 620, 4.6, "9979000006", "6 years"),
    ]
    for w in ahmedabad_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "Ahmedabad", "state": "Gujarat", "country": "India", "price": w[3], "price_currency": "INR", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    # ── UAE ────────────────────────────────────

    dubai_workers = [
        ("Mohammed Al Rashid", "Plumber", "Dubai Marina", 150, 4.7, "+97150000001", "8 years"),
        ("Rajan Thomas", "Electrician", "Jumeirah", 180, 4.8, "+97150000002", "12 years"),
        ("Sanjay Pillai", "Driver", "Downtown Dubai", 200, 4.9, "+97150000003", "10 years"),
        ("Maria Santos", "Maid", "Palm Jumeirah", 120, 4.6, "+97150000004", "6 years"),
        ("Priya Krishnan", "Cook", "Business Bay", 160, 4.8, "+97150000005", "8 years"),
        ("Ahmed Hassan", "AC Mechanic", "Deira", 200, 4.7, "+97150000006", "9 years"),
        ("Filippo Reyes", "Babysitter", "JBR", 140, 4.9, "+97150000007", "5 years"),
        ("Sunil Mathew", "Carpenter", "Al Barsha", 170, 4.6, "+97150000008", "11 years"),
        ("Rajesh Nambiar", "Security Guard", "DIFC", 160, 4.5, "+97150000009", "7 years"),
        ("Lakshmi Iyer", "Caretaker/Nurse", "Mirdif", 180, 4.9, "+97150000010", "8 years"),
    ]
    for w in dubai_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "Dubai", "state": "Dubai", "country": "UAE", "price": w[3], "price_currency": "AED", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    abudhabi_workers = [
        ("Khalid Al Mansoori", "Plumber", "Corniche", 160, 4.6, "+97155000001", "7 years"),
        ("Binoy George", "Electrician", "Al Reem Island", 190, 4.8, "+97155000002", "11 years"),
        ("Anoop Menon", "Driver", "Yas Island", 210, 4.7, "+97155000003", "9 years"),
        ("Joanna Cruz", "Maid", "Khalidiyah", 130, 4.5, "+97155000004", "5 years"),
        ("Sunitha Nair", "Cook", "Al Mushrif", 170, 4.8, "+97155000005", "7 years"),
    ]
    for w in abudhabi_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "Abu Dhabi", "state": "Abu Dhabi", "country": "UAE", "price": w[3], "price_currency": "AED", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    # ── UK ─────────────────────────────────────

    london_workers = [
        ("James O'Brien", "Plumber", "Shoreditch", 80, 4.7, "+44790000001", "10 years"),
        ("David Patel", "Electrician", "Canary Wharf", 90, 4.8, "+44790000002", "12 years"),
        ("Maria Garcia", "Maid", "Chelsea", 60, 4.6, "+44790000003", "6 years"),
        ("Rajesh Sharma", "Driver", "Heathrow", 100, 4.9, "+44790000004", "15 years"),
        ("Priya Singh", "Cook", "Southall", 75, 4.8, "+44790000005", "8 years"),
        ("Michael Brown", "Carpenter", "Hackney", 95, 4.6, "+44790000006", "11 years"),
        ("Sophie Williams", "Babysitter", "Kensington", 65, 4.9, "+44790000007", "4 years"),
        ("Arjun Mehta", "AC Mechanic", "Croydon", 85, 4.7, "+44790000008", "8 years"),
        ("Emma Johnson", "Caretaker/Nurse", "Wimbledon", 80, 4.9, "+44790000009", "9 years"),
        ("Tom Wilson", "Gardener", "Richmond", 70, 4.6, "+44790000010", "7 years"),
        ("Anita Kapoor", "Tutor", "Wembley", 90, 4.9, "+44790000011", "6 years"),
    ]
    for w in london_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "London", "state": "England", "country": "UK", "price": w[3], "price_currency": "GBP", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    # ── SINGAPORE ──────────────────────────────

    singapore_workers = [
        ("Wei Ming Tan", "Plumber", "Orchard", 120, 4.7, "+6591000001", "8 years"),
        ("Kumar Selvam", "Electrician", "Jurong East", 140, 4.8, "+6591000002", "10 years"),
        ("Maria dela Cruz", "Maid", "Buona Vista", 80, 4.6, "+6591000003", "5 years"),
        ("Raj Chandran", "Driver", "Tampines", 160, 4.8, "+6591000004", "12 years"),
        ("Siti Rahmah", "Cook", "Toa Payoh", 110, 4.9, "+6591000005", "7 years"),
        ("John Lim", "Carpenter", "Woodlands", 130, 4.6, "+6591000006", "9 years"),
        ("Priya Nair", "Babysitter", "Holland Village", 100, 4.8, "+6591000007", "4 years"),
        ("Ahmad Fauzi", "AC Mechanic", "Bedok", 150, 4.7, "+6591000008", "8 years"),
        ("Grace Tan", "Caretaker/Nurse", "Clementi", 130, 4.9, "+6591000009", "7 years"),
        ("Ravi Subramaniam", "Security Guard", "Changi", 140, 4.5, "+6591000010", "10 years"),
    ]
    for w in singapore_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "Singapore", "state": "Singapore", "country": "Singapore", "price": w[3], "price_currency": "SGD", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    # ── USA ─────────────────────────────────────

    newyork_workers = [
        ("Carlos Mendez", "Plumber", "Brooklyn", 120, 4.6, "+12120000001", "9 years"),
        ("Robert Johnson", "Electrician", "Manhattan", 140, 4.8, "+12120000002", "13 years"),
        ("Ana Ramirez", "Maid", "Queens", 80, 4.5, "+12120000003", "5 years"),
        ("James Williams", "Driver", "Bronx", 130, 4.7, "+12120000004", "11 years"),
        ("Priya Patel", "Cook", "Jackson Heights", 100, 4.9, "+12120000005", "8 years"),
        ("David Chen", "Carpenter", "Staten Island", 150, 4.6, "+12120000006", "10 years"),
        ("Sofia Rodriguez", "Babysitter", "Upper East Side", 110, 4.9, "+12120000007", "4 years"),
        ("Michael Davis", "Gardener", "Long Island City", 95, 4.5, "+12120000008", "7 years"),
    ]
    for w in newyork_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "New York", "state": "New York", "country": "USA", "price": w[3], "price_currency": "USD", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    sf_workers = [
        ("Miguel Torres", "Plumber", "Mission District", 130, 4.7, "+14150000001", "8 years"),
        ("Kevin Zhang", "Electrician", "SoMa", 155, 4.8, "+14150000002", "11 years"),
        ("Gabriela Flores", "Maid", "Sunset District", 90, 4.6, "+14150000003", "5 years"),
        ("Rajiv Nair", "Driver", "Financial District", 140, 4.8, "+14150000004", "10 years"),
        ("Amy Nguyen", "Cook", "Richmond District", 110, 4.9, "+14150000005", "7 years"),
        ("Jake Miller", "Gym Trainer", "Castro", 160, 4.9, "+14150000006", "5 years"),
        ("Lisa Park", "Dog Walker", "Noe Valley", 80, 4.8, "+14150000007", "3 years"),
    ]
    for w in sf_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "San Francisco", "state": "California", "country": "USA", "price": w[3], "price_currency": "USD", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    # ── CANADA ─────────────────────────────────

    toronto_workers = [
        ("Harpreet Singh", "Plumber", "Brampton", 110, 4.6, "+14160000001", "8 years"),
        ("Navdeep Kaur", "Maid", "Scarborough", 75, 4.5, "+14160000002", "5 years"),
        ("Gurpreet Dhaliwal", "Driver", "Mississauga", 120, 4.7, "+14160000003", "10 years"),
        ("Aisha Khan", "Cook", "North York", 95, 4.8, "+14160000004", "7 years"),
        ("Patrick O'Neill", "Electrician", "Downtown Toronto", 130, 4.8, "+14160000005", "11 years"),
        ("Sarah Thompson", "Caretaker/Nurse", "Etobicoke", 110, 4.9, "+14160000006", "8 years"),
    ]
    for w in toronto_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "Toronto", "state": "Ontario", "country": "Canada", "price": w[3], "price_currency": "CAD", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    # ── AUSTRALIA ──────────────────────────────

    sydney_workers = [
        ("Liam O'Connor", "Plumber", "Bondi", 130, 4.7, "+61400000001", "9 years"),
        ("Priya Sharma", "Maid", "Parramatta", 85, 4.5, "+61400000002", "5 years"),
        ("Raj Patel", "Electrician", "Chatswood", 150, 4.8, "+61400000003", "12 years"),
        ("Emma Wilson", "Babysitter", "Manly", 95, 4.9, "+61400000004", "4 years"),
        ("Wei Chen", "Gardener", "Ryde", 100, 4.6, "+61400000005", "6 years"),
        ("Mohammed Ali", "Driver", "Liverpool", 120, 4.7, "+61400000006", "10 years"),
    ]
    for w in sydney_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "Sydney", "state": "New South Wales", "country": "Australia", "price": w[3], "price_currency": "AUD", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    # ── GERMANY ────────────────────────────────

    berlin_workers = [
        ("Klaus Mueller", "Plumber", "Mitte", 90, 4.7, "+49301000001", "10 years"),
        ("Hans Weber", "Electrician", "Prenzlauer Berg", 100, 4.8, "+49301000002", "13 years"),
        ("Anna Schmidt", "Maid", "Charlottenburg", 70, 4.6, "+49301000003", "6 years"),
        ("Mehmet Yilmaz", "Carpenter", "Kreuzberg", 95, 4.5, "+49301000004", "9 years"),
        ("Fatima Al-Hassan", "Cook", "Neukolln", 80, 4.8, "+49301000005", "7 years"),
        ("Thomas Fischer", "Gardener", "Steglitz", 75, 4.6, "+49301000006", "8 years"),
    ]
    for w in berlin_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "Berlin", "state": "Berlin", "country": "Germany", "price": w[3], "price_currency": "EUR", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    # ── JAPAN ──────────────────────────────────

    tokyo_workers = [
        ("Tanaka Hiroshi", "Plumber", "Shinjuku", 8000, 4.8, "+81901000001", "10 years"),
        ("Yamamoto Kenji", "Electrician", "Shibuya", 9000, 4.9, "+81901000002", "12 years"),
        ("Sato Yuki", "Maid", "Minato", 6500, 4.7, "+81901000003", "5 years"),
        ("Nakamura Taro", "Carpenter", "Asakusa", 8500, 4.7, "+81901000004", "9 years"),
        ("Suzuki Akiko", "Caretaker/Nurse", "Setagaya", 9000, 4.9, "+81901000005", "8 years"),
        ("Kobayashi Ryo", "Gardener", "Meguro", 7000, 4.6, "+81901000006", "7 years"),
    ]
    for w in tokyo_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "Tokyo", "state": "Tokyo", "country": "Japan", "price": w[3], "price_currency": "JPY", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    # ── SOUTH AFRICA ───────────────────────────

    joburg_workers = [
        ("Sipho Dlamini", "Plumber", "Sandton", 800, 4.6, "+27821000001", "7 years"),
        ("Thabo Mokoena", "Electrician", "Soweto", 900, 4.7, "+27821000002", "10 years"),
        ("Nomsa Zulu", "Maid", "Rosebank", 600, 4.5, "+27821000003", "5 years"),
        ("Bongani Nkosi", "Driver", "Midrand", 1000, 4.8, "+27821000004", "12 years"),
        ("Lerato Khumalo", "Cook", "Melville", 750, 4.8, "+27821000005", "7 years"),
    ]
    for w in joburg_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "Johannesburg", "state": "Gauteng", "country": "South Africa", "price": w[3], "price_currency": "ZAR", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    # ── BRAZIL ─────────────────────────────────

    saopaulo_workers = [
        ("Carlos Silva", "Plumber", "Jardins", 150, 4.5, "+55111000001", "7 years"),
        ("Ana Costa", "Maid", "Moema", 100, 4.4, "+55111000002", "5 years"),
        ("Roberto Santos", "Electrician", "Vila Madalena", 170, 4.7, "+55111000003", "9 years"),
        ("Maria Oliveira", "Cook", "Pinheiros", 130, 4.8, "+55111000004", "7 years"),
        ("Paulo Ferreira", "Driver", "Santo Andre", 160, 4.6, "+55111000005", "11 years"),
    ]
    for w in saopaulo_workers:
        workers.append({"name": w[0], "skill": w[1], "area": w[2], "city": "Sao Paulo", "state": "Sao Paulo", "country": "Brazil", "price": w[3], "price_currency": "BRL", "rating": w[4], "phone": w[5], "experience": w[6], "available": True, "verified": True})

    return workers


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "RozgarBot API is running!", "version": "6.0", "workers_global": True})


@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "alive", "time": datetime.now().isoformat()})


@app.route("/seed-workers", methods=["POST"])
def seed_workers():
    try:
        workers = generate_workers()
        workers_col.delete_many({})
        workers_col.insert_many(workers)
        return jsonify({"message": f"{len(workers)} workers seeded successfully across multiple countries!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/chat", methods=["POST"])
def chat():
    try:
        body = request.get_json(force=True)
        user_message = body.get("message", "").strip()
        user_name = body.get("user_name", "").strip() or "there"

        if not user_message:
            return jsonify({
                "reply": f"Hi {user_name}! How can I help you today? Tell me what kind of worker you need and your location.",
                "workers": [],
                "quick_replies": ["Find a Plumber", "Need an Electrician", "Book a Maid", "Hire a Driver"],
                "booking_card": None,
                "booking_confirmed": False
            })

        if len(user_message) < 2 or not re.search(r'[a-zA-Z]', user_message):
            return jsonify({
                "reply": f"Hi {user_name}! Please describe what service you need and your location (e.g. 'I need a plumber in Dubai').",
                "workers": [],
                "quick_replies": ["Find a Plumber", "Need an Electrician", "Book a Maid", "Hire a Driver"],
                "booking_card": None,
                "booking_confirmed": False
            })

        all_workers = list(workers_col.find({"available": True}, {"_id": 0}))
        workers_str = json.dumps(all_workers, ensure_ascii=False)

        prompt = (
            "You are RozgarBot — a global AI-powered platform connecting daily-wage workers with households and businesses worldwide.\n\n"
            "Available Workers Database:\n" + workers_str + "\n\n"
            "User's name: " + user_name + "\n"
            "User's message: \"" + user_message + "\"\n\n"
            "STRICT RULES:\n"
            "1. ALWAYS address the user as \"" + user_name + "\" — NEVER call them 'Guest' or 'User'\n"
            "2. If user asks for multiple workers or a skill, return ALL matching workers\n"
            "3. Reply ONLY in English — professional, friendly tone\n"
            "4. Match workers by skill, city, area, country based on user's message\n"
            "5. If no workers match, reply helpfully suggesting alternatives\n"
            "6. Return STRICTLY valid JSON only — no extra text, no markdown\n\n"
            "EXACT JSON FORMAT:\n"
            "{\"reply\": \"message here\", \"workers\": [{\"name\": \"\", \"skill\": \"\", \"area\": \"\", \"city\": \"\", \"country\": \"\", \"price\": 0, \"price_currency\": \"\", \"rating\": 0.0, \"phone\": \"\", \"experience\": \"\"}], \"quick_replies\": [\"btn1\", \"btn2\", \"btn3\"], \"booking_card\": null}\n\n"
            "workers = [] if no match. booking_card = null always."
        )

        raw_reply = call_ai(prompt)
        parsed = extract_json_from_text(raw_reply)

        booking_confirmed = False

        if parsed:
            workers_with_score = []
            for w in parsed.get("workers", []):
                w["match_score"] = calculate_match_score(w, user_message)
                workers_with_score.append(w)
            workers_with_score.sort(key=lambda x: x.get("match_score", 0), reverse=True)

            booking_words = ["book", "confirm", "hire", "need", "send", "yes", "ok", "sure", "get me", "arrange"]
            if any(word in user_message.lower() for word in booking_words):
                for worker in all_workers:
                    skill_match = worker.get("skill", "").lower() in user_message.lower()
                    area_match = worker.get("area", "").lower() in user_message.lower()
                    city_match = worker.get("city", "").lower() in user_message.lower()
                    name_match = worker.get("name", "").lower() in user_message.lower()
                    if skill_match or area_match or city_match or name_match:
                        booking = create_booking(worker, user_name)
                        booking_confirmed = True
                        parsed["booking_card"] = {
                            "worker": worker,
                            "status": "confirmed",
                            "booking_id": booking["booking_id"],
                            "message": f"{worker['name']} will contact you within 30 minutes. Booking confirmed!"
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
                "reply": raw_reply if raw_reply else "Please try again.",
                "workers": [],
                "quick_replies": ["Find a Plumber", "Need an Electrician", "Book a Maid", "Hire a Driver"],
                "booking_card": None,
                "booking_confirmed": False
            })

    except Exception as e:
        return jsonify({
            "reply": "Something went wrong on our end. Please try again in a moment.",
            "workers": [],
            "quick_replies": ["Try again"],
            "booking_card": None,
            "booking_confirmed": False
        }), 200


@app.route("/workers", methods=["GET"])
def get_workers():
    try:
        country = request.args.get("country", "")
        city = request.args.get("city", "")
        skill = request.args.get("skill", "")
        query = {"available": True}
        if country:
            query["country"] = {"$regex": country, "$options": "i"}
        if city:
            query["city"] = {"$regex": city, "$options": "i"}
        if skill:
            query["skill"] = {"$regex": skill, "$options": "i"}
        workers = list(workers_col.find(query, {"_id": 0}))
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
            return jsonify({"error": "booking_id is required"}), 400
        result = bookings_col.update_one(
            {"booking_id": booking_id},
            {"$set": {"status": "cancelled", "cancelled_at": datetime.now().isoformat()}}
        )
        if result.matched_count == 0:
            return jsonify({"error": "Booking not found"}), 404
        return jsonify({"message": "Booking cancelled successfully.", "booking_id": booking_id})
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
            return jsonify({"error": "worker_name and rating are required"}), 400

        review = {
            "worker_name": worker_name,
            "user_name": user_name,
            "rating": float(rating),
            "review": review_text,
            "created_at": datetime.now().isoformat()
        }
        reviews_col.insert_one(review)

        all_reviews = list(reviews_col.find({"worker_name": worker_name}, {"_id": 0}))
        avg = sum(r["rating"] for r in all_reviews) / len(all_reviews)
        workers_col.update_one({"name": worker_name}, {"$set": {"rating": round(avg, 1)}})

        return jsonify({"message": "Rating submitted successfully. Thank you!", "new_avg_rating": round(avg, 1)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/stats", methods=["GET"])
def get_stats():
    try:
        total_workers = workers_col.count_documents({"available": True})
        total_bookings = bookings_col.count_documents({})
        confirmed_bookings = bookings_col.count_documents({"status": "confirmed"})
        cancelled_bookings = bookings_col.count_documents({"status": "cancelled"})
        countries = workers_col.distinct("country")

        skill_pipeline = [
            {"$group": {"_id": "$skill", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}, {"$limit": 8}
        ]
        popular_skills = list(workers_col.aggregate(skill_pipeline))

        city_pipeline = [
            {"$group": {"_id": "$city", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        city_demand = list(workers_col.aggregate(city_pipeline))

        booking_skill_pipeline = [
            {"$group": {"_id": "$worker_skill", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}, {"$limit": 5}
        ]
        top_booked_skills = list(bookings_col.aggregate(booking_skill_pipeline))

        return jsonify({
            "total_workers": total_workers,
            "total_countries": len(countries),
            "countries": countries,
            "total_bookings": total_bookings,
            "confirmed_bookings": confirmed_bookings,
            "cancelled_bookings": cancelled_bookings,
            "popular_skills": popular_skills,
            "city_demand": city_demand,
            "top_booked_skills": top_booked_skills
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
