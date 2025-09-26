from django.urls import path
from .views import home, ask_view, inbox, inbox_detail, mark_reviewed, export_csv

app_name = 'questions'
urlpatterns = [
    path('', home, name='home'),                 # raiz /
    path('ask/', ask_view, name='ask'),
    path('inbox/', inbox, name='inbox'),
    path('inbox/<int:pk>/', inbox_detail, name='inbox_detail'),
    path('inbox/<int:pk>/reviewed/', mark_reviewed, name='mark_reviewed'),
    path('inbox/export.csv', export_csv, name='export_csv'),
]