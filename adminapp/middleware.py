from django.utils.deprecation import MiddlewareMixin
from django.views.decorators.cache import never_cache

class DisableAdminCacheMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if request.path.startswith('/adminpanel/'):  # or your admin URL prefix
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, private, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        return response
