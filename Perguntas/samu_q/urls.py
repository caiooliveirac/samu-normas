from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # login/logout curtos
    path('login/',  auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # ainda mantemos as rotas padrão /accounts/ caso queira
    path('accounts/', include('django.contrib.auth.urls')),

    # index -> inbox
    path('', RedirectView.as_view(pattern_name='questions:inbox', permanent=False)),
    path('', include('questions.urls')),
    path('faq/', include('faq.urls')),
]
