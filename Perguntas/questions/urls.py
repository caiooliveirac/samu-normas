from django.urls import path
from . import views
from .views import home, ask_view, inbox, inbox_detail, mark_reviewed, export_csv, api_search_log

app_name = 'questions'
urlpatterns = [
    path("", views.rules_home, name="rules_home"),
    path("api/rules/", views.api_rules, name="api_rules"),
    path("api/search-log/", api_search_log, name="api_search_log"),
    path('ask/', views.ask_view, name='ask'),
    path('inbox/', views.inbox, name='inbox'),
    path('inbox/<int:pk>/', views.inbox_detail, name='inbox_detail'),
    path('inbox/<int:pk>/reviewed/', views.mark_reviewed, name='mark_reviewed'),
    path('inbox/export.csv', views.export_csv, name='export_csv'),
]