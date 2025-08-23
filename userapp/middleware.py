from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout
from django.urls import reverse 

from django.utils.cache import add_never_cache_headers



class NoCacheForAuthenticatedMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        # If user is authenticated, prevent caching
        if request.user.is_authenticated:
            add_never_cache_headers(response)
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