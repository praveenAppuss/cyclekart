# utils/otp.py
import random
from django.core.mail import send_mail
from django.conf import settings

def generate_otp():
    """Generate a 6-digit OTP."""
    return str(random.randint(100000, 999999))

def send_otp_email(email, otp, purpose="Email Verification"):
    """Send OTP to the provided email."""
    subject = f'CycleKart - {purpose}'
    message = f'Your OTP is: {otp}'
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )