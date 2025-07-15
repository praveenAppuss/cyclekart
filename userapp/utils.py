from django.utils.decorators import decorator_from_middleware
from django.utils.cache import patch_cache_control
from django.utils.deprecation import MiddlewareMixin

class NoCacheMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        patch_cache_control(response,
                            no_cache=True,
                            no_store=True,
                            must_revalidate=True,
                            max_age=0)
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

no_cache_view = decorator_from_middleware(NoCacheMiddleware)
