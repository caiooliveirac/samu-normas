from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.http import HttpResponse

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
]