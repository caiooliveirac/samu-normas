from django.urls import path
from . import views

app_name = 'scoreboard'

urlpatterns = [
    path('', views.scoreboard_view, name='home'),
    path('data/', views.scoreboard_data, name='data'),
    path('faculdade/<str:short_name>/', views.faculty_detail, name='faculty_detail'),
    path('modalidade/<int:pk>/', views.modality_detail, name='modality_detail'),
]
