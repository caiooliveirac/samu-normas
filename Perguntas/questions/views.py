"""Views da app `questions`.

Além das páginas de regras e inbox de perguntas, este módulo também implementa o fluxo de
checklists da USA e o envio de um resumo (digest) no Telegram.

Pontos de integração principais:
- Fonte do checklist: `docs/checklist.md` (e opcionalmente `docs/checklist_compact.md`).
- Inbox (staff): `/inbox/checklists/`.
- Envio de digest (staff): `POST /api/checklists/digest/send/` (suporta `slot` e `force`).
"""

from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.db.models import Prefetch, Q
from .models import (
    Rule,
    RuleCard,
    RuleBullet,
    Category,
    Tag,
    Question,
    ChecklistSubmission,
    ChecklistDigestLog,
    SearchLog,
    AskedTerm,
)
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django import forms
import csv
import json
import datetime
import re
import urllib.request
import urllib.error
from pathlib import Path
from django.conf import settings
import unicodedata

# (Removido import duplicado de Question, Rule)


def staff_required(view_func):
    return user_passes_test(
        lambda u: getattr(u, 'is_staff', False),
        login_url='/login/',
        redirect_field_name='next',
    )(view_func)


EXPECTED_AMBULANCES = [
    'SM01',
    'CB02',
    'PR03',
    'PM04',
    'BR05',
    'CN10',
    'PP20',
    'IT30',
    'PM40',
    'CZ50',
    'BR60',
    'CC70',
]


def _normalize_unit(value: str) -> str:
    """Normaliza o identificador da unidade (ex.: SM01).

    Regras:
    - Remove separadores (espaço, hífen, etc.) e deixa em caixa alta.
    - Tolera entradas como "SM 01" / "SM-01".
    - Tolera entradas como "SM1" e converte para "SM01".
    """
    s = (value or '').strip().upper()
    # Mantém só A-Z/0-9 para tolerar "SM 01", "SM-01", etc.
    s = re.sub(r'[^A-Z0-9]+', '', s)

    # Alguns envios podem vir sem o zero à esquerda (SM1, PM4, BR5).
    if re.fullmatch(r'[A-Z]{2}\d', s):
        s = s[:2] + '0' + s[2:]
    return s


_CHECKLIST_COMPACT_MAP = None


def _norm_label_key(label: str) -> str:
    s = _strip_accents((label or '').strip()).upper()
    s = re.sub(r'[^A-Z0-9]+', '', s)
    return s


def _extract_task_items_from_md(md: str):
    items = []
    for raw in (md or '').splitlines():
        m = re.match(r'^\s*-\s*\[\s*[xX ]\s*\]\s*(.+?)\s*$', raw)
        if m:
            items.append(m.group(1).strip())
    return items


def _load_checklist_compact_map():
    """Mapa {label_completo -> label_curto}.

    Opcional: se existir docs/checklist_compact.md, usa task-lists na mesma ordem
    do docs/checklist.md para permitir apelidos editáveis pelo time.
    """
    global _CHECKLIST_COMPACT_MAP
    if _CHECKLIST_COMPACT_MAP is not None:
        return _CHECKLIST_COMPACT_MAP

    base = Path(getattr(settings, 'BASE_DIR', Path.cwd()))
    full_path = base / 'docs' / 'checklist.md'
    compact_path = base / 'docs' / 'checklist_compact.md'

    try:
        full_md = full_path.read_text(encoding='utf-8')
    except Exception:
        full_md = ''
    full_items = _extract_task_items_from_md(full_md)

    if not compact_path.exists():
        _CHECKLIST_COMPACT_MAP = {}
        return _CHECKLIST_COMPACT_MAP

    try:
        compact_md = compact_path.read_text(encoding='utf-8')
    except Exception:
        compact_md = ''
    compact_items = _extract_task_items_from_md(compact_md)

    if not full_items or len(full_items) != len(compact_items):
        _CHECKLIST_COMPACT_MAP = {}
        return _CHECKLIST_COMPACT_MAP

    m = {}
    for i, full_label in enumerate(full_items):
        short_label = (compact_items[i] or '').strip()
        if short_label:
            m[_norm_label_key(full_label)] = short_label
    _CHECKLIST_COMPACT_MAP = m
    return _CHECKLIST_COMPACT_MAP


def _strip_accents(s: str) -> str:
    s = s or ''
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def _smart_title(s: str) -> str:
    """Title case preservando siglas curtas (DEA, O2, etc.)."""
    parts = []
    for w in (s or '').split():
        if w.isupper() and len(w) <= 4:
            parts.append(w)
        else:
            parts.append(w[:1].upper() + w[1:].lower() if w else w)
    return ' '.join(parts).strip()


def _compact_label(label: str) -> str:
    # Primeiro tenta mapa editável (se houver)
    label = (label or '').strip()
    if not label:
        return ''

    # Normaliza quebras/whitespace para evitar rótulos com "\n" no meio
    label = re.sub(r'\s+', ' ', label).strip()

    m = _load_checklist_compact_map()
    lookup = label
    # Campos podem vir preenchidos como "CHECADA EM: 2026-01-17"; para mapear,
    # usamos somente o lado esquerdo antes dos valores.
    if ':' in lookup:
        lookup = lookup.split(':', 1)[0].strip()
    mapped = m.get(_norm_label_key(lookup))
    if mapped:
        return mapped.strip()

    # Heurística: remove detalhes para caber em mensagens curtas
    t = label
    t = t.split('— Obs:', 1)[0].strip()
    t = re.sub(r'\s*\([^)]*\)\s*', ' ', t).strip()
    t = t.split(';', 1)[0].strip()
    t = t.split('—', 1)[0].strip()
    # Se tiver "RADIO/CELULAR", prioriza o primeiro termo
    if '/' in t:
        t = t.split('/', 1)[0].strip()

    words = t.split()
    if len(words) > 3:
        t = ' '.join(words[:3])

    t = _strip_accents(t)
    t = _smart_title(t)
    return t

def _extract_missing_and_obs(text: str, *, compact: bool = False):
    """Extrai itens marcados como faltando (🚫) e observações (— Obs:).

    - compact=False: retorna strings praticamente iguais ao texto salvo (para debug/leitura).
    - compact=True: retorna labels curtos (para inbox/telegram).
    """
    missing = []
    obs = []
    for raw in (text or '').splitlines():
        line = raw.strip()
        if not line:
            continue

        # Observações (✅ ou 🚫)
        if '— Obs:' in line:
            if compact:
                clean = line.lstrip('✅🚫').strip()
                left, right = clean.split('— Obs:', 1)
                lbl = _compact_label(left.strip())
                msg = (right or '').strip()
                if msg:
                    obs.append(f"{lbl}: {msg}" if lbl else msg)
            else:
                obs.append(line)

        # Itens faltando
        if line.startswith('🚫'):
            body = line.lstrip('🚫').strip()
            body_no_obs = body.split('— Obs:', 1)[0].strip()
            missing.append(_compact_label(body_no_obs) if compact else body)

    return missing, obs


def _send_telegram_message(text: str):
    token = (getattr(settings, 'TELEGRAM_BOT_TOKEN', '') or '').strip()
    chat_ids = list(getattr(settings, 'TELEGRAM_CHAT_IDS', []) or [])
    if not token or not chat_ids:
        return {
            'ok': False,
            'error': 'Telegram não configurado (defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID(S)).',
            'sent_to': [],
        }

    api = f"https://api.telegram.org/bot{token}/sendMessage"

    def _split_for_telegram(full_text: str, max_len: int = 3500):
        full_text = (full_text or '').strip('\n')
        if len(full_text) <= max_len:
            return [full_text]

        lines = full_text.splitlines()
        chunks = []
        buf = []
        buf_len = 0
        for line in lines:
            # +1 por causa do \n ao juntar
            extra = len(line) + (1 if buf else 0)
            if buf and (buf_len + extra) > max_len:
                chunks.append('\n'.join(buf).strip())
                buf = [line]
                buf_len = len(line)
            else:
                buf.append(line)
                buf_len += extra
        if buf:
            chunks.append('\n'.join(buf).strip())

        if len(chunks) <= 1:
            return chunks

        total = len(chunks)
        labeled = []
        for i, c in enumerate(chunks, start=1):
            labeled.append(f"(parte {i}/{total})\n{c}")
        return labeled

    chunks = _split_for_telegram(text)
    sent_to = []
    last_error = None

    for chat_id in chat_ids:
        ok_for_this_chat = True
        for part in chunks:
            payload = {
                'chat_id': chat_id,
                'text': part,
                'disable_web_page_preview': True,
            }
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(api, data=data, headers={'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    body = resp.read().decode('utf-8', errors='replace')
                    if resp.status != 200:
                        last_error = f"HTTP {resp.status}: {body[:300]}"
                        ok_for_this_chat = False
                        break
            except urllib.error.HTTPError as e:
                try:
                    body = e.read().decode('utf-8', errors='replace')
                except Exception:
                    body = ''
                last_error = f"HTTPError {getattr(e, 'code', '?')}: {body[:300]}"
                ok_for_this_chat = False
                break
            except Exception as e:
                last_error = str(e)
                ok_for_this_chat = False
                break

        if ok_for_this_chat:
            sent_to.append(chat_id)

    if sent_to:
        return {'ok': True, 'sent_to': sent_to, 'error': None}
    return {'ok': False, 'sent_to': [], 'error': last_error or 'Falha ao enviar no Telegram.'}


def _build_checklist_digest_for_date(day: datetime.date):
    expected = [u for u in EXPECTED_AMBULANCES]
    expected_norm = {_normalize_unit(u): u for u in expected}

    submissions_for_day = (
        ChecklistSubmission.objects.filter(created_at__date=day)
        .order_by('-created_at', '-id')
    )
    latest_by_unit = {}
    for s in submissions_for_day:
        nu = _normalize_unit(s.unit)
        if nu in expected_norm and nu not in latest_by_unit:
            latest_by_unit[nu] = s

    missing_units = [expected_norm[k] for k in expected_norm.keys() if k not in latest_by_unit]

    lines = []
    now_local = timezone.localtime(timezone.now())
    lines.append(f"Checklist USA — {day.isoformat()} — {now_local:%H:%M}")

    if missing_units:
        lines.append("Sem envio: " + ", ".join(missing_units))
    else:
        lines.append("Sem envio: (nenhuma) ✅")

    # Faltas/obs por unidade (na ordem esperada, em blocos para leitura)
    flagged = []
    for display in expected:
        nu = _normalize_unit(display)
        s = latest_by_unit.get(nu)
        if not s:
            continue
        missing_items, obs_items = _extract_missing_and_obs(s.text, compact=True)
        if not missing_items and not obs_items:
            continue

        flagged.append(f"• {display}")
        if missing_items:
            flagged.append("  Faltas: " + ", ".join(missing_items))
        if obs_items:
            flagged.append("  Obs: " + "; ".join(obs_items))
        # Linha em branco entre unidades para leitura no Telegram
        flagged.append("")

    # Remove linha em branco final
    while flagged and not flagged[-1].strip():
        flagged.pop()

    if flagged:
        lines.append("")
        lines.append("Faltas/Obs:")
        lines.extend(flagged)
    else:
        lines.append("")
        lines.append("Faltas/Obs: (nenhuma sinalizada)")

    text = "\n".join(lines)
    return {
        'date': day,
        'message': text,
        'missing_units': missing_units,
        'flagged_lines': flagged,
    }

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

@staff_required
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

@staff_required
def inbox_detail(request, pk):
    obj = Question.objects.get(pk=pk)
    return render(request, 'questions/inbox_detail.html', {'q': obj})

@staff_required
def mark_reviewed(request, pk):
    obj = Question.objects.get(pk=pk)
    obj.status = 'reviewed'
    obj.save()
    messages.success(request, f'Pergunta #{obj.pk} marcada como revisada.')
    return redirect('questions:inbox_detail', pk=obj.pk)

@staff_required
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


@staff_required
def inbox_checklists(request):
    q = request.GET.get('q', '').strip()
    day = request.GET.get('date', '').strip()  # YYYY-MM-DD

    qs = ChecklistSubmission.objects.all().order_by('-created_at', '-id')

    parsed_date = None
    if day:
        try:
            parsed_date = datetime.date.fromisoformat(day)
            qs = qs.filter(created_at__date=parsed_date)
        except ValueError:
            messages.error(request, 'Data inválida. Use o formato AAAA-MM-DD.')
    else:
        parsed_date = timezone.localdate()
        day = parsed_date.isoformat()
        qs = qs.filter(created_at__date=parsed_date)

    if q:
        qs = qs.filter(
            Q(doctor_name__icontains=q)
            | Q(unit__icontains=q)
            | Q(text__icontains=q)
        )

    page_obj = Paginator(qs, 20).get_page(request.GET.get('page'))

    # Resumo do dia selecionado: quais ambulâncias já têm checklist hoje?
    expected = [u for u in EXPECTED_AMBULANCES]
    expected_norm = {_normalize_unit(u): u for u in expected}

    # Considera apenas unidades do dia selecionado.
    present_norm = set()
    for unit in qs.values_list('unit', flat=True).distinct():
        nu = _normalize_unit(unit)
        if nu in expected_norm:
            present_norm.add(nu)

    missing = [expected_norm[k] for k in expected_norm.keys() if k not in present_norm]
    present = [expected_norm[k] for k in expected_norm.keys() if k in present_norm]

    # Resumo por dia (janela curta) para organização.
    window_days = 14
    start_date = parsed_date - datetime.timedelta(days=window_days - 1)
    recent = (
        ChecklistSubmission.objects.filter(created_at__date__gte=start_date)
        .values_list('created_at__date', 'unit')
        .order_by('-created_at__date')
    )
    by_date = {}
    for d, unit in recent:
        if d not in by_date:
            by_date[d] = {'count': 0, 'present_norm': set()}
        by_date[d]['count'] += 1
        nu = _normalize_unit(unit)
        if nu in expected_norm:
            by_date[d]['present_norm'].add(nu)

    daily_summary = []
    for i in range(window_days):
        d = parsed_date - datetime.timedelta(days=i)
        info = by_date.get(d)
        count = info['count'] if info else 0
        present_for_day = info['present_norm'] if info else set()
        missing_for_day = [expected_norm[k] for k in expected_norm.keys() if k not in present_for_day]
        daily_summary.append(
            {
                'date': d,
                'date_iso': d.isoformat(),
                'count': count,
                'missing': missing_for_day,
                'missing_count': len(missing_for_day),
            }
        )

    # Resumo por unidade (do dia): pega o envio mais recente por unidade e extrai faltas/obs do texto.
    submissions_for_day = (
        ChecklistSubmission.objects.filter(created_at__date=parsed_date)
        .order_by('-created_at', '-id')
    )
    latest_by_unit = {}
    for s in submissions_for_day:
        nu = _normalize_unit(s.unit)
        if nu in expected_norm and nu not in latest_by_unit:
            latest_by_unit[nu] = s

    unit_summaries = []
    for nu, display in expected_norm.items():
        s = latest_by_unit.get(nu)
        if not s:
            unit_summaries.append(
                {
                    'unit': display,
                    'has_submission': False,
                    'missing_count': None,
                    'obs_count': None,
                    'missing_preview': [],
                    'obs_preview': [],
                    'detail_url': None,
                    'doctor_name': None,
                    'created_at': None,
                }
            )
            continue

        missing_items, obs_items = _extract_missing_and_obs(s.text, compact=True)
        unit_summaries.append(
            {
                'unit': display,
                'has_submission': True,
                'missing_count': len(missing_items),
                'obs_count': len(obs_items),
                'missing_preview': missing_items[:6],
                'obs_preview': obs_items[:4],
                'detail_url': f"/inbox/checklists/{s.id}/",
                'doctor_name': s.doctor_name,
                'created_at': s.created_at,
            }
        )

    return render(
        request,
        'questions/inbox_checklists.html',
        {
            'page_obj': page_obj,
            'q': q,
            'date': day,
            'expected_units': expected,
            'present_units': present,
            'missing_units': missing,
            'daily_summary': daily_summary,
            'unit_summaries': unit_summaries,
        },
    )


@staff_required
def inbox_checklists_detail(request, pk):
    obj = ChecklistSubmission.objects.get(pk=pk)
    return render(request, 'questions/inbox_checklists_detail.html', {'s': obj})

def rules_home(request):
    # carrega só pra mostrar o shell do app; os dados vêm via fetch
    return render(request, "questions/home_rules_react.html")


def _slugify(s: str) -> str:
    s = (s or '').strip().lower()
    s = re.sub(r'[^a-z0-9\-\s_]+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'[\s_]+', '-', s).strip('-')
    return s or 'item'


def _parse_checklist_md(md: str):
    """Parser simples para o formato padronizado em docs/checklist.md.

    Regras:
    - Grupos: linhas iniciando com '## '
    - Subgrupos: linhas iniciando com '### ' (opcional)
    - Itens: task list '- [ ] ' ou '- [x] '
    """
    groups = []
    current_group = None
    current_sub = None

    for raw in (md or '').splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('<!--'):
            continue

        if line.startswith('## '):
            current_group = {
                'title': line[3:].strip(),
                'items': [],
                'subgroups': [],
            }
            groups.append(current_group)
            current_sub = None
            continue

        if line.startswith('### '):
            if not current_group:
                continue
            current_sub = {
                'title': line[4:].strip(),
                'items': [],
            }
            current_group['subgroups'].append(current_sub)
            continue

        m = re.match(r'^-\s*\[(?P<state>[ xX])\]\s+(?P<label>.+)$', line)
        if m:
            label = m.group('label').strip()
            checked = m.group('state').strip().lower() == 'x'

            # Heurística: alguns itens são campos para preenchimento (lacre/datas), não apenas checkbox.
            label_upper = label.upper()
            is_field = (
                label_upper.startswith('LACRE')
                or 'PREENCHER DATA' in label_upper
                or label_upper.startswith('CHECADA EM')
                or label_upper.startswith('DATA DA PRÓXIMA TROCA')
            )

            group_key = _slugify(current_group['title'] if current_group else 'geral')
            sub_key = _slugify(current_sub['title'] if current_sub else '')
            item_key = _slugify(label)
            item_id = '-'.join([p for p in [group_key, sub_key, item_key] if p])

            item = {
                'id': item_id,
                'label': label,
                'checked': checked,
                'kind': 'field' if is_field else 'checkbox',
            }
            if current_sub is not None:
                current_sub['items'].append(item)
            elif current_group is not None:
                current_group['items'].append(item)
            else:
                # Itens antes de qualquer grupo vão para um grupo "Geral"
                current_group = {'title': 'GERAL', 'items': [item], 'subgroups': []}
                groups.append(current_group)
            continue

    return groups


def checklists_usa(request):
    md_path = Path(settings.BASE_DIR) / 'docs' / 'checklist.md'
    if md_path.is_file():
        md = md_path.read_text(encoding='utf-8')
    else:
        md = ''
    groups = _parse_checklist_md(md)
    return render(
        request,
        'questions/checklists_usa.html',
        {
            'groups': groups,
            'expected_units': EXPECTED_AMBULANCES,
        },
    )


@require_http_methods(["POST"])
def api_checklists_submit(request):
    try:
        raw = (request.body or b'').decode('utf-8')
        payload = json.loads(raw or '{}')
    except Exception:
        return JsonResponse({"ok": False, "error": "JSON inválido."}, status=400)

    doctor_name = str(payload.get('doctor_name', '') or '').strip()
    unit = str(payload.get('unit', '') or '').strip()
    text = str(payload.get('text', '') or '').strip()

    if not doctor_name:
        return JsonResponse({"ok": False, "error": "Nome do médico é obrigatório."}, status=400)
    if not unit:
        return JsonResponse({"ok": False, "error": "Unidade é obrigatória."}, status=400)
    if not text:
        return JsonResponse({"ok": False, "error": "Texto do checklist é obrigatório."}, status=400)

    if len(doctor_name) > 120:
        return JsonResponse({"ok": False, "error": "Nome do médico muito longo."}, status=400)
    if len(unit) > 120:
        return JsonResponse({"ok": False, "error": "Unidade muito longa."}, status=400)
    if len(text) > 50000:
        return JsonResponse({"ok": False, "error": "Texto muito longo."}, status=400)

    submission = ChecklistSubmission(
        doctor_name=doctor_name,
        unit=unit,
        text=text,
        user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:300],
    )
    try:
        submission.set_ip(get_client_ip(request))
    except Exception:
        pass
    submission.save()

    return JsonResponse(
        {
            "ok": True,
            "id": submission.pk,
            "created_at": submission.created_at.isoformat() if submission.created_at else None,
        }
    )


@staff_required
@require_http_methods(["POST"])
def api_checklists_send_digest(request):
    # Entrada: date=YYYY-MM-DD (opcional), slot=manual|morning|midday|evening (opcional), force=1 (opcional)
    day_raw = (request.POST.get('date') or '').strip()
    slot = (request.POST.get('slot') or 'manual').strip()[:32]
    force = (request.POST.get('force') or '').strip() in ('1', 'true', 'yes', 'on')

    if day_raw:
        try:
            day = datetime.date.fromisoformat(day_raw)
        except ValueError:
            return JsonResponse({'ok': False, 'error': 'Data inválida (use AAAA-MM-DD).'}, status=400)
    else:
        day = timezone.localdate()

    if not force:
        exists = ChecklistDigestLog.objects.filter(date=day, slot=slot, status='success').exists()
        if exists:
            return JsonResponse({'ok': True, 'skipped': True, 'reason': 'already_sent'})

    digest = _build_checklist_digest_for_date(day)
    msg = digest['message']

    send = _send_telegram_message(msg)
    status = 'success' if send.get('ok') else 'error'
    recipient = ','.join(send.get('sent_to') or [])

    try:
        ChecklistDigestLog.objects.update_or_create(
            date=day,
            slot=slot,
            defaults={
                'sent_at': timezone.now(),
                'status': status,
                'recipient': recipient,
                'message': msg,
                'error': (send.get('error') or '')[:4000],
            },
        )
    except Exception:
        # Mesmo se o log falhar, não quebra o envio.
        pass

    if not send.get('ok'):
        return JsonResponse({'ok': False, 'error': send.get('error') or 'Falha ao enviar.'}, status=500)

    return JsonResponse({'ok': True, 'sent_to': send.get('sent_to') or [], 'skipped': False})

def api_rules(request):
    # carrega tudo já ordenado (Rule → Cards → Bullets → Tags)
    rules = (
        Rule.objects.filter(is_published=True)
        .select_related("category")
        .prefetch_related(
            Prefetch(
                "cards",
                queryset=RuleCard.objects.filter(is_published=True)
                .order_by("order", "id")
                .prefetch_related(
                    Prefetch(
                        "bullets",
                        queryset=RuleBullet.objects.all()
                        .order_by("order", "id")
                        .prefetch_related("tags"),
                    )
                ),
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
                card_obj["bullets"].append(
                    {
                        "id": b.id,
                        "text": b.text,
                        "tags": [t.name for t in b.tags.all()],
                    }
                )
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
