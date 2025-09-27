import os
import re
from datetime import datetime, timedelta

import firebase_admin
import pytz
from dateutil.parser import parse as dtparse
from firebase_admin import credentials, firestore, initialize_app
from firebase_functions import https_fn
from flask import Flask, jsonify, request
from flask_cors import CORS

# --- Initialization ---

# Initialize Flask App and CORS
# Using CORS allows your web frontend to make requests to this function
app = Flask(__name__)
CORS(app, origins=["https://gomovo-2a655.web.app", "https://gomovo-2a655.firebaseapp.com", "http://localhost:3000", "http://127.0.0.1:3000"])

# Initialize Firebase Admin SDK
# This allows your function to securely communicate with Firestore
def get_db():
    """Initialize and return Firestore client."""
    try:
        if not firebase_admin._apps:
            initialize_app()
        return firestore.client()
    except ValueError:
        # App already initialized
        return firestore.client()
    except Exception as e:
        print(f"Firebase Admin SDK initialization failed: {e}")
        # Fallback for local development if a key file is present
        if os.path.exists('service-account.json'):
            try:
                cred = credentials.Certificate('service-account.json')
                firebase_admin.initialize_app(cred)
                return firestore.client()
            except Exception as fallback_e:
                print(f"Fallback initialization with service-account.json also failed: {fallback_e}")
                return None
        else:
            print("Default credentials failed and service-account.json not found. Firestore will not be available.")
            return None
APP_TZ = pytz.timezone("Asia/Qatar")

# --- Helper Functions ---

def _parse_and_make_naive(dt_str: str) -> datetime:
    """Parses a datetime string and returns a naive datetime object."""
    dt = dtparse(dt_str)
    return datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, 0)

def valid_email(email: str) -> bool:
    """Validates an email address format."""
    if not email:
        return True # Email is optional
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None

# --- API Routes ---

@app.route('/bookings', methods=['GET'])
def get_bookings():
    """API endpoint to retrieve bookings for a specific date."""
    date_q = request.args.get("date")
    if not date_q:
        return jsonify({"error": "Date parameter is required"}), 400

    try:
        selected_date = datetime.strptime(date_q, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400
    
    day_start = APP_TZ.localize(datetime(selected_date.year, selected_date.month, selected_date.day))
    day_end = day_start + timedelta(days=1)

    try:
        db = get_db()
        if not db:
            return jsonify({"error": "Database connection failed"}), 500
        
        bookings_collection = db.collection('bookings')
        # Get all bookings and filter in memory (simpler for now)
        docs = bookings_collection.stream()

        bookings = []
        total_minutes = 0
        for doc in docs:
            b = doc.to_dict()
            b['id'] = doc.id
            
            # Convert Firestore Timestamps to timezone-aware datetime objects for calculation
            start_dt_utc = b['start_at']
            end_dt_utc = b['end_at']
            
            # Convert to App Timezone
            start_dt = start_dt_utc.astimezone(APP_TZ)
            end_dt = end_dt_utc.astimezone(APP_TZ)

            # Filter bookings that overlap with the selected day
            if start_dt < day_end and end_dt > day_start:
                # Calculate the portion of the booking that falls on the selected day
                s = max(start_dt, day_start)
                e = min(end_dt, day_end)
                total_minutes += max(0, int((e - s).total_seconds() // 60))

                # Format for frontend response
                b['start_at'] = start_dt.strftime("%Y-%m-%d %H:%M")
                b['end_at'] = end_dt.strftime("%Y-%m-%d %H:%M")
                bookings.append(b)
            
        bookings.sort(key=lambda x: x['start_at'])
        hours_booked = round(total_minutes / 60, 2)
        
        return jsonify({
            "bookings": bookings,
            "todays_count": len(bookings),
            "hours_booked": hours_booked
        })
    except Exception as e:
        return jsonify({"error": f"An error occurred: {e}"}), 500


@app.route('/book', methods=['POST'])
def create_booking():
    """API endpoint to create a new booking."""
    data = request.get_json()
    title = data.get("title", "").strip()
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    start_raw = data.get("start_at", "")
    end_raw = data.get("end_at", "")

    if not all([title, name, start_raw, end_raw]):
        return jsonify({"message": "الرجاء تعبئة جميع الحقول المطلوبة."}), 400

    if not valid_email(email):
        return jsonify({"message": "صيغة البريد الإلكتروني غير صحيحة."}), 400

    try:
        start_at_naive = _parse_and_make_naive(start_raw)
        end_at_naive = _parse_and_make_naive(end_raw)
        start_at = APP_TZ.localize(start_at_naive)
        end_at = APP_TZ.localize(end_at_naive)
    except Exception:
        return jsonify({"message": "صيغة الوقت غير صحيحة."}), 400

    if end_at.date() == start_at.date() and end_at.time() < start_at.time():
        end_at += timedelta(days=1)

    now_in_qatar = datetime.now(APP_TZ)
    if start_at < now_in_qatar:
        return jsonify({"message": "لا يمكن إنشاء حجز في وقت قد مضى."}), 400

    if end_at <= start_at:
        return jsonify({"message": "وقت النهاية يجب أن يكون بعد وقت البداية."}), 400

    if (end_at - start_at) > timedelta(hours=6):
        return jsonify({"message": "المدة القصوى للحجز 6 ساعات."}), 400

    try:
        db = get_db()
        if not db:
            return jsonify({"message": "خطأ في الاتصال بقاعدة البيانات"}), 500
        
        bookings_collection = db.collection('bookings')
        # Check for conflicts by getting all bookings and filtering in memory
        all_bookings = bookings_collection.stream()
        
        for doc in all_bookings:
            existing = doc.to_dict()
            existing_start = existing['start_at'].astimezone(APP_TZ)
            existing_end = existing['end_at'].astimezone(APP_TZ)
            
            # Check if there's an overlap
            if start_at < existing_end and end_at > existing_start:
                msg = (f"عذرًا، هناك تعارض مع حجز آخر: "
                       f"'{existing['title']}'")
                return jsonify({"message": msg}), 409

        new_booking = {
            "title": title,
            "name": name,
            "email": email or None,
            "start_at": start_at,
            "end_at": end_at,
            "created_at": datetime.now(pytz.utc) # Store in UTC
        }
        bookings_collection.add(new_booking)

        return jsonify({"message": "تم إنشاء الحجز بنجاح ✅"}), 201
    except Exception as e:
        return jsonify({"message": f"An error occurred: {e}"}), 500


@app.route('/delete/<string:booking_id>', methods=['DELETE'])
def delete_booking(booking_id):
    """API endpoint to delete a booking."""
    try:
        db = get_db()
        if not db:
            return jsonify({"message": "خطأ في الاتصال بقاعدة البيانات"}), 500
        
        bookings_collection = db.collection('bookings')
        bookings_collection.document(booking_id).delete()
        return jsonify({"message": "تم حذف الحجز."}), 200
    except Exception as e:
        return jsonify({"message": f"خطأ أثناء الحذف: {e}"}), 500

# --- Cloud Function Wrapper ---
# This wraps the entire Flask app in a single Cloud Function.
# The name 'api' is the entry point that Firebase will use.
@https_fn.on_request()
def api(req: https_fn.Request) -> https_fn.Response:
    """Wraps the Flask app in a Cloud Function for deployment."""
    with app.request_context(req.environ):
        return app.full_dispatch_request()

