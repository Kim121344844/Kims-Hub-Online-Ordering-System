from flask import flash
from flask_mail import Message
from models import db, OTP
from app import mail
import random
import datetime

def generate_otp():
    """Generate a 6-digit random OTP."""
    return str(random.randint(100000, 999999))

def send_otp_email(email, name, otp):
    """Send OTP via email."""
    try:
        msg = Message('Your Login OTP', recipients=[email])
        msg.body = f"Hi {name},\n\nYour login OTP code is: {otp}\nThis code expires in 5 minutes."
        mail.send(msg)
        return True
    except Exception as e:
        print("Error sending login OTP:", e)
        return False

def store_otp_in_db(email, otp):
    """Store OTP in database."""
    new_otp = OTP(email=email, otp_code=otp, timestamp=datetime.datetime.now())
    db.session.add(new_otp)
    db.session.commit()
    return new_otp

def verify_otp_from_db(email, otp_input):
    """Verify OTP from database."""
    # Get the latest unused OTP for this email
    stored_otp = OTP.query.filter_by(email=email, used=False).order_by(OTP.timestamp.desc()).first()
    if not stored_otp:
        return False, "No OTP found. Please try logging in again."

    # Check expiry (5 minutes)
    if datetime.datetime.now() - stored_otp.timestamp > datetime.timedelta(minutes=5):
        db.session.delete(stored_otp)
        db.session.commit()
        return False, "OTP expired. Please login again."

    # Check OTP match
    if otp_input == stored_otp.otp_code:
        stored_otp.used = True
        db.session.commit()
        return True, "Login successful!"
    else:
        return False, "Invalid OTP. Try again."
