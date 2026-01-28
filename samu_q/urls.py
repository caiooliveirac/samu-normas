from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.middleware.csrf import get_token

def healthz(_):
    return HttpResponse("ok", content_type="text/plain")

urlpatterns = [
    path('admin/', admin.site.urls),

    # login/logout usando nosso template
    path('login/',  auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # apps do projeto (inclui a rota '' -> home definida em questions/urls.py)
    path('', include('questions.urls')),

    # healthcheck
    path('healthz', healthz),
    # versão / build info
    path('__version__', lambda _:
         JsonResponse({
             'sha': getattr(settings, 'BUILD_SHA', 'unknown'),
             'version': getattr(settings, 'APP_VERSION', 'unknown'),
             'build_date': getattr(settings, 'BUILD_DATE', 'unknown'),
         })),
    path('csrf-test', ensure_csrf_cookie(lambda r: JsonResponse({
        'csrf_cookie': r.COOKIES.get('csrftoken'),
        'csrf_token_func': get_token(r),
        'secure_flags': {
            'session_cookie_secure': getattr(settings, 'SESSION_COOKIE_SECURE', None),
            'csrf_cookie_secure': getattr(settings, 'CSRF_COOKIE_SECURE', None),
            'secure_ssl_redirect': getattr(settings, 'SECURE_SSL_REDIRECT', None),
        },
        'trusted_origins': getattr(settings, 'CSRF_TRUSTED_ORIGINS', []),
        'allowed_hosts': settings.ALLOWED_HOSTS,
    }))),
]