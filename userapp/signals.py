from allauth.account.signals import user_signed_up
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
import random

@receiver(user_signed_up)
def handle_google_signup(request, user, **kwargs):
    user.is_active = False
    user.save()

    otp = str(random.randint(100000, 999999))
    request.session['otp'] = otp
    request.session['signup_data'] = {
        'email': user.email,
        'username': user.username,
        'mobile': '',  # Since Google won’t return mobile
        'password': user.password  # This will be unusable but needed for logic
    }

    send_mail(
        subject='CycleKart - Email Verification (Google)',
        message=f'Your OTP is: {otp}',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
