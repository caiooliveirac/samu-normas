from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.db.models import Prefetch
from .models import Rule, RuleCard, RuleBullet, Category, Tag, Question
from django import forms
import csv

from .models import Question, Rule

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
            try:
                q.set_ip(get_client_ip(request))
            except Exception:
                pass
            q.save()
            messages.success(request, 'Pergunta enviada. Obrigado!')
            return redirect('questions:ask')
        else:
            messages.error(request, 'Corrija os erros no formulário.')
    else:
        form = AskForm()
    return render(request, 'questions/ask.html', {'form': form})

@staff_member_required
def inbox(request):
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    qs = Question.objects.all().order_by('-id')
    if q:
        qs = qs.filter(text__icontains=q)
    if status in ['new','reviewed']:
        qs = qs.filter(status=status)
    page_obj = Paginator(qs, 15).get_page(request.GET.get('page'))
    return render(request, 'questions/inbox.html', {'page_obj': page_obj, 'q': q, 'status': status})

@staff_member_required
def inbox_detail(request, pk):
    obj = Question.objects.get(pk=pk)
    return render(request, 'questions/inbox_detail.html', {'q': obj})

@staff_member_required
def mark_reviewed(request, pk):
    obj = Question.objects.get(pk=pk)
    obj.status = 'reviewed'
    obj.save()
    messages.success(request, f'Pergunta #{obj.pk} marcada como revisada.')
    return redirect('questions:inbox_detail', pk=obj.pk)

@staff_member_required
def export_csv(request):
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    qs = Question.objects.all().order_by('-id')
    if q:
        qs = qs.filter(text__icontains=q)
    if status in ['new','reviewed']:
        qs = qs.filter(status=status)
    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename="perguntas.csv"'
    w = csv.writer(resp); w.writerow(['id','created_at','status','category','text'])
    for row in qs.values_list('id','created_at','status','category','text'):
        w.writerow(row)
    return resp

def rules_home(request):
    # carrega só pra mostrar o shell do app; os dados vêm via fetch
    return render(request, "questions/home_rules_react.html")

def api_rules(request):
    # carrega tudo já ordenado (Rule → Cards → Bullets → Tags)
    rules = (
        Rule.objects.filter(is_published=True)
        .select_related("category")
        .prefetch_related(
            Prefetch(
                "cards",
                queryset=RuleCard.objects.filter(is_published=True).order_by("order", "id").prefetch_related(
                    Prefetch(
                        "bullets",
                        queryset=RuleBullet.objects.all().order_by("order", "id").prefetch_related("tags")
                    )
                )
            )
        )
        .order_by("order", "title")
    )

    data = []
    for r in rules:
        rule_obj = {
            "id": r.id,
            "title": r.title,
            "slug": r.slug,
            "category": r.category.name if r.category else "",
            "cards": [],
        }
        for c in r.cards.all():
            card_obj = {
                "id": c.id,
                "title": c.title or "",
                "bullets": [],
            }
            for b in c.bullets.all():
                card_obj["bullets"].append({
                    "id": b.id,
                    "text": b.text,
                    "tags": [t.name for t in b.tags.all()],
                })
            rule_obj["cards"].append(card_obj)
        data.append(rule_obj)

    return JsonResponse({"results": data})

# ----- NOVO: Página inicial (/) listando Rules publicadas -----
def home(request):
    rules = Rule.objects.filter(is_published=True).order_by('order','title')[:500]
    return render(request, 'questions/home.html', {'rules': rules})
