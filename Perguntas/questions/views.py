from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django import forms
from .models import Question

class AskForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'category']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Escreva sua pergunta...'}),
            'category': forms.TextInput(attrs={'placeholder': 'Opcional: categoria'}),
        }

def get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')

@require_http_methods(["GET", "POST"])
def ask_view(request):
    if request.method == 'POST':
        form = AskForm(request.POST)
        if form.is_valid():
            q = form.save(commit=False)
            # mantém hash de IP para moderação futura (opcional)
            q.set_ip(get_client_ip(request))
            q.save()
            messages.success(request, 'Pergunta enviada. Obrigado!')
            return redirect('questions:ask')
        else:
            messages.error(request, 'Corrija os erros no formulário.')
    else:
        form = AskForm()
    return render(request, 'questions/ask.html', {'form': form})


from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.http import HttpResponse
import csv

@staff_member_required
def inbox(request):
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    qs = Question.objects.all().order_by('-id')
    if q:
        qs = qs.filter(text__icontains=q)
    if status in ['new', 'reviewed']:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 15)  # 15 por página
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'questions/inbox.html', {
        'page_obj': page_obj,
        'q': q,
        'status': status,
    })

@staff_member_required
def inbox_detail(request, pk):
    obj = Question.objects.get(pk=pk)
    return render(request, 'questions/inbox_detail.html', {'q': obj})

@staff_member_required
def mark_reviewed(request, pk):
    obj = Question.objects.get(pk=pk)
    obj.status = 'reviewed'
    obj.save()
    from django.contrib import messages
    messages.success(request, f'Pergunta #{obj.pk} marcada como revisada.')
    from django.shortcuts import redirect
    return redirect('questions:inbox_detail', pk=obj.pk)

@staff_member_required
def export_csv(request):
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    qs = Question.objects.all().order_by('-id')
    if q:
        qs = qs.filter(text__icontains=q)
    if status in ['new', 'reviewed']:
        qs = qs.filter(status=status)

    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename="perguntas.csv"'
    writer = csv.writer(resp)
    writer.writerow(['id','created_at','status','category','text'])
    for row in qs.values_list('id','created_at','status','category','text'):
        writer.writerow(row)
    return resp
