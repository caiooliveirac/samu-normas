from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.db.models import Prefetch
from .models import Rule, RuleCard, RuleBullet, Category, Tag, Question, SearchLog, AskedTerm
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
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
            # --- Atualiza AskedTerm ---
            try:
                import re
                text = (q.text or "").strip()
                if text:
                    tokens = re.findall(r"[\wÀ-ÖØ-öø-ÿ]{4,}", text, flags=re.UNICODE)
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
                            # first_seen e last_seen já setados por default
                            obj.count = 1
                            obj.save(update_fields=["count"])  # garante consistência
                        else:
                            from django.utils import timezone as _tz
                            obj.count = obj.count + 1
                            obj.last_seen = _tz.now()
                            obj.save(update_fields=["count", "last_seen"])
            except Exception:
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
    """Recebe uma frase/pesquisa e registra cada palavra (>=4 letras) que
    resultou em zero resultados na busca do front. Agora:
    - Entrada JSON: {"term": "frase completa", "results_count": 0}
      (results_count refere-se ao total de resultados gerais da busca.)
    - Tokeniza a frase e salva cada palavra >=4 letras individualmente.
    - Ignora palavras repetidas nas últimas 2h (case-insensitive).
    Resposta: {"logged": [...], "ignored": {"short": [...], "recent": [...]}}
    Status 201 se ao menos uma palavra foi gravada; caso contrário 200.
    """
    try:
        import json, re
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({"error": "invalid json"}, status=400)

    phrase = (payload.get("term") or "").strip()
    results_count = int(payload.get("results_count") or 0)
    if not phrase:
        return JsonResponse({"error": "empty term"}, status=400)

    # Só registramos se a busca geral retornou zero (ou poucos) resultados.
    # Mantemos regra original de só registrar quando zero.
    if results_count != 0:
        return JsonResponse({"ignored": True, "reason": "non_zero_results"}, status=200)

    # Tokenização: palavras com letras/números (unicode), tamanho >=4
    tokens = re.findall(r"[\wÀ-ÖØ-öø-ÿ]{4,}", phrase, flags=re.UNICODE)
    if not tokens:
        return JsonResponse({"ignored": True, "reason": "no_tokens"}, status=200)

    from datetime import timedelta
    cutoff = timezone.now() - timedelta(hours=2)

    ip = get_client_ip(request)
    try:
        ip_h = hash_ip(ip)
    except Exception:
        ip_h = ""
    ua = (request.META.get('HTTP_USER_AGENT') or '')[:300]

    logged = []
    ignored_short = []  # (mantido para possível relatório futuro)
    ignored_recent = []

    # Normaliza (casefold para melhor comparação em pt-BR) e de-dup dentro da própria frase
    seen_local = set()
    for raw in tokens:
        word = raw.strip()
        if not word:
            continue
        lower = word.casefold()
        if lower in seen_local:
            continue
        seen_local.add(lower)

        if len(word) < 4:
            ignored_short.append(word)
            continue
        # Checa se já existe esse termo nas últimas 2h
        exists = SearchLog.objects.filter(term__iexact=word, created_at__gte=cutoff).exists()
        if exists:
            ignored_recent.append(word)
            continue
        # Cria registro
        SearchLog.objects.create(
            term=word[:200],
            results_count=0,
            ip_hash=ip_h,
            user_agent=ua,
        )
        logged.append(word)

    status_code = 201 if logged else 200
    return JsonResponse({
        "logged": logged,
        "ignored": {"short": ignored_short, "recent": ignored_recent},
        "total_phrase": phrase,
    }, status=status_code)

# ----- NOVO: Página inicial (/) listando Rules publicadas -----
def home(request):
    rules = Rule.objects.filter(is_published=True).order_by('order','title')[:500]
    return render(request, 'questions/home.html', {'rules': rules})
