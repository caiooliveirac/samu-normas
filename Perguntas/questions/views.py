from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.db.models import Prefetch
from .models import (
    Rule,
    RuleCard,
    RuleBullet,
    Category,
    Tag,
    Question,
    SearchLog,
    AskedTerm,
)
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django import forms
import csv

# (Removido import duplicado de Question, Rule)

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
            # --- Atualiza AskedTerm ---
            try:
                _update_asked_terms(q.text)
            except Exception:
                # Mantém aplicação resiliente mesmo se algo falhar
                pass
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


@csrf_exempt
@require_http_methods(["POST"])
def api_search_log(request):
    """Registra termos (>=4 chars) de buscas sem resultado.
    Entrada JSON: {"term": "frase", "results_count": 0}
    - Só processa quando results_count == 0
    - Dedup local + janela de 2h (não repete termo recente)
    """
    import json
    import re
    from datetime import timedelta

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "invalid json"}, status=400)

    phrase = (payload.get("term") or "").strip()
    results_count = int(payload.get("results_count") or 0)
    if not phrase:
        return JsonResponse({"error": "empty term"}, status=400)
    if results_count != 0:
        return JsonResponse({"ignored": True, "reason": "non_zero_results"}, status=200)

    tokens = re.findall(r"[\wÀ-ÖØ-öø-ÿ]{4,}", phrase, flags=re.UNICODE)
    if not tokens:
        return JsonResponse({"ignored": True, "reason": "no_tokens"}, status=200)

    cutoff = timezone.now() - timedelta(hours=2)
    ip = get_client_ip(request)
    try:
        ip_h = hash_ip(ip)
    except Exception:
        ip_h = ""
    ua = (request.META.get("HTTP_USER_AGENT") or "")[:300]

    logged = []
    ignored_short = []
    ignored_recent = []
    seen_local = set()
    for raw in tokens:
        w = raw.strip()
        if not w:
            continue
        key = w.casefold()
        if key in seen_local:
            continue
        seen_local.add(key)

        if len(w) < 4:
            ignored_short.append(w)
            continue
        # Checa se já existe esse termo nas últimas 2h
        exists = SearchLog.objects.filter(term__iexact=w, created_at__gte=cutoff).exists()
        if exists:
            ignored_recent.append(w)
            continue
        # Cria registro
        SearchLog.objects.create(
            term=w[:200],
            results_count=0,
            ip_hash=ip_h,
            user_agent=ua,
        )
        logged.append(w)

    status_code = 201 if logged else 200
    return JsonResponse(
        {
            "logged": logged,
            "ignored": {"short": ignored_short, "recent": ignored_recent},
            "total_phrase": phrase,
        },
        status=status_code,
    )

# ----- NOVO: Página inicial (/) listando Rules publicadas -----
def home(request):
    rules = Rule.objects.filter(is_published=True).order_by('order','title')[:500]
    return render(request, 'questions/home.html', {'rules': rules})


# ----------------- Funções utilitárias internas (lazy) -----------------
def _update_asked_terms(text: str):
    """Extrai termos de uma pergunta e atualiza contadores de AskedTerm.
    Executado somente durante submissão de nova pergunta.
    """
    if not text:
        return
    import re
    from django.utils import timezone as _tz
    tokens = re.findall(r"[\wÀ-ÖØ-öø-ÿ]{4,}", (text or "").strip(), flags=re.UNICODE)
    if not tokens:
        return
    seen = set()
    for raw in tokens:
        w = raw.strip()
        if not w or len(w) < 4:
            continue
        key = w.casefold()
        if key in seen:
            continue
        seen.add(key)
        obj, created = AskedTerm.objects.get_or_create(term=w[:200])
        if created:
            obj.count = 1
            obj.save(update_fields=["count"])
        else:
            obj.count = obj.count + 1
            obj.last_seen = _tz.now()
            obj.save(update_fields=["count", "last_seen"])
