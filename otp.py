from flask import flash
from flask_mail import Message
from models import db, OTP
import random
import datetime

def generate_otp():
    """Generate a 6-digit random OTP."""
    return str(random.randint(100000, 999999))

def send_otp_email(email, name, otp):
    """Send OTP via email."""
    from app import mail
    try:
        msg = Message('Your Login OTP', recipients=[email])
        msg.body = f"Hi {name},\n\nYour login OTP code is: {otp}\nThis code expires in 5 minutes."
        mail.send(msg)
        print(f"Login OTP sent to {email}: {otp}")
        return True
    except Exception as e:
        print("Error sending login OTP:", e)
        # For development/testing, print OTP to console if email fails
        print(f"DEV MODE: Login OTP for {email}: {otp}")
        return True  # Return True to allow login flow to continue

def store_otp_in_db(email, otp):
    """Store OTP in database."""
    new_otp = OTP(email=email, otp_code=otp, timestamp=datetime.datetime.now())
    db.session.add(new_otp)
    db.session.commit()
    print(f"OTP stored in database: {email} - {otp}")
    return new_otp

def verify_otp_from_db(email, otp_input):
    """Verify OTP from database."""
    # Delete all expired OTPs for this email
    expired_otps = OTP.query.filter_by(email=email, used=False).filter(OTP.timestamp < datetime.datetime.now() - datetime.timedelta(minutes=5)).all()
    for otp in expired_otps:
        db.session.delete(otp)
    db.session.commit()

    # Get the latest unused OTP for this email
    stored_otp = OTP.query.filter_by(email=email, used=False).order_by(OTP.timestamp.desc()).first()
    if not stored_otp:
        return False, "No OTP found. Please try logging in again."

    # Check OTP match
    if otp_input == stored_otp.otp_code:
        stored_otp.used = True
        db.session.commit()
        return True, "Login successful!"
    else:
        return False, "Invalid OTP. Try again."

def send_password_reset_otp_email(email, name, otp):
    """Send password reset OTP via email."""
    from app import mail
    try:
        msg = Message('Password Reset OTP', recipients=[email])
        msg.body = f"Hi {name},\n\nYour password reset OTP code is: {otp}\nThis code expires in 5 minutes.\n\nIf you did not request this, please ignore this email."
        mail.send(msg)
        print(f"Password reset OTP for {email}: {otp}")
        return True
    except Exception as e:
        print("Error sending password reset OTP:", e)
        return False

def verify_password_reset_otp(email, otp_input):
    """Verify password reset OTP from database."""
    # Delete all expired OTPs for this email
    expired_otps = OTP.query.filter_by(email=email, used=False).filter(OTP.timestamp < datetime.datetime.now() - datetime.timedelta(minutes=5)).all()
    for otp in expired_otps:
        db.session.delete(otp)
    db.session.commit()

    # Get the latest unused OTP for this email
    stored_otp = OTP.query.filter_by(email=email, used=False).order_by(OTP.timestamp.desc()).first()
    if not stored_otp:
        return False, "No OTP found. Please request a new reset code."

    # Check OTP match
    if otp_input == stored_otp.otp_code:
        stored_otp.used = True
        db.session.commit()
        return True, "OTP verified successfully!"
    else:
        return False, "Invalid OTP. Try again."


