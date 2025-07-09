from allauth.account.signals import user_signed_up
from django.dispatch import receiver

@receiver(user_signed_up)
def handle_google_signup(request, user, **kwargs):
    sociallogin = kwargs.get('sociallogin')

    if sociallogin:
        # ✅ Google login → auto activate
        user.is_active = True
        user.save()
        return

    # Normal signup → OTP flow
    from django.core.mail import send_mail
    from django.conf import settings
    import random

    user.is_active = False
    user.save()

    otp = str(random.randint(100000, 999999))
    request.session['otp'] = otp
    request.session['signup_data'] = {
        'email': user.email,
        'username': user.username,
        'mobile': '',
        'password': user.password
    }

    send_mail(
        subject='CycleKart - Email Verification',
        message=f'Your OTP is: {otp}',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
