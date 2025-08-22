from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout
from django.urls import reverse 


class DisableCacheMiddleware(MiddlewareMixin): 
    def process_response(self, request, response):
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    
class BlockedUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user

        if user.is_authenticated and not user.is_superuser:
            if user.is_blocked:
                logout(request)
                messages.error(request, "Your account has been blocked by admin.")
                return redirect(reverse('login'))

        response = self.get_response(request)
        return response