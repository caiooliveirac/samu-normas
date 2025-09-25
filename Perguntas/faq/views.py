from django.shortcuts import render

def home(request):
    return render(request, 'faq/index.html')
