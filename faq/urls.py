from django.urls import path
from .views import home

app_name = 'faq'
urlpatterns = [
    path('', home, name='home'),
]
