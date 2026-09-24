"""Área da coordenação: entrada pelo escala, painel, edição de card com audit log."""
import hashlib
import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .federacao import ler_token_handoff
from .models import CardRevision, Question, Rule, RuleBullet, RuleCard
from .views import staff_required

log = logging.getLogger(__name__)


def _federacao_ligada() -> bool:
    return bool(settings.ESCALA_URL and settings.ESCALA_FEDERACAO_SECRET)


def _rotulo_usuario(user) -> str:
    nome = user.get_full_name() or user.username
    return f"{nome} <{user.email}>" if user.email and user.email != nome else nome


# --- Entrada -----------------------------------------------------------------

def entrar(request):
    """Botão "Área da coordenação": já logado vai direto; senão, pelo escala."""
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("questions:painel")
    if _federacao_ligada():
        return redirect(f"{settings.ESCALA_URL}/api/auth/handoff?para={settings.FEDERACAO_ID}")
    return redirect("/login/?next=/painel/")


def _negado(request, mensagem, status):
    return render(request, "questions/painel_negado.html", {"mensagem": mensagem}, status=status)


def sso(request):
    """Destino do handoff do escala: valida o token e abre a sessão local.

    A identidade é o e-mail autenticado pelo escala; conta local nasce na hora
    (sem senha utilizável) para quem tem perfil de coordenação lá.
    """
    if not _federacao_ligada():
        raise Http404
    claims = ler_token_handoff(request.GET.get("token", ""), settings.ESCALA_FEDERACAO_SECRET, settings.FEDERACAO_ID)
    if claims is None:
        log.warning("[federacao] token recusado")
        return _negado(request, "O link de entrada expirou ou é inválido. Tente de novo pelo botão.", 401)

    email = claims["sub"].strip().lower()
    perfil = claims.get("perfil", "")
    origem = claims.get("origem", "")
    user = User.objects.filter(email__iexact=email).first() or User.objects.filter(username__iexact=email).first()
    if origem not in settings.FEDERACAO_ORIGENS or perfil not in settings.FEDERACAO_PERFIS:
        log.info("[federacao] recusado email=%s perfil=%s origem=%s", email, perfil or "-", origem or "-")
        # conta que só existe pela federação perde o staff junto com o perfil;
        # conta local (com senha) é gerida no /admin/ e não é tocada
        if user is not None and user.is_staff and not user.has_usable_password():
            user.is_staff = False
            user.save(update_fields=["is_staff"])
        return _negado(request, "A área da coordenação é restrita a administradores e coordenadores do escala.", 403)

    if user is None:
        user = User(username=email[:150], email=email)
        user.set_unusable_password()
    if not user.is_active:
        return _negado(request, "Sua conta neste manual está desativada.", 403)
    nome = (claims.get("nome") or "").strip()
    if nome and not user.get_full_name():
        user.first_name = nome[:150]
    user.is_staff = True
    user.save()

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.set_expiry(settings.FEDERACAO_SESSAO_SEGUNDOS)
    log.info("[federacao] login_ok email=%s perfil=%s origem=%s", email, perfil, origem)
    return redirect("questions:painel")


def api_me(request):
    """O React pergunta isto para decidir se mostra os botões de edição."""
    u = request.user
    coord = bool(u.is_authenticated and u.is_staff)
    return JsonResponse({"coordenacao": coord, "nome": (u.get_full_name() or u.username) if coord else ""})


# --- Painel ------------------------------------------------------------------

@staff_required
def painel(request):
    rules = Rule.objects.prefetch_related("cards").order_by("order", "title")
    return render(request, "questions/painel.html", {
        "novas": Question.objects.filter(status=Question.STATUS_NEW).count(),
        "ultimas_perguntas": Question.objects.order_by("-id")[:5],
        "ultimas_alteracoes": CardRevision.objects.select_related("card")[:5],
        "rules": rules,
    })


# --- Edição de card ------------------------------------------------------------

def _snapshot(card) -> dict:
    return {
        "title": card.title,
        "is_published": card.is_published,
        "bullets": [{"id": b.id, "text": b.text} for b in card.bullets.order_by("order", "id")],
    }


def _versao(snap: dict) -> str:
    return hashlib.sha256(json.dumps(snap, sort_keys=True).encode()).hexdigest()[:16]


@staff_required
@require_http_methods(["GET", "POST"])
def card_editar(request, pk):
    card = get_object_or_404(RuleCard.objects.select_related("rule"), pk=pk)

    if request.method == "POST":
        with transaction.atomic():
            card = RuleCard.objects.select_for_update().select_related("rule").get(pk=pk)
            antes = _snapshot(card)
            if request.POST.get("versao") != _versao(antes):
                messages.error(request, "Este card foi alterado por outra pessoa enquanto você editava. Suas mudanças não foram salvas — confira a versão atual.")
                return redirect("questions:card_editar", pk=pk)

            titulo = request.POST.get("title", "").strip()
            if not titulo:
                messages.error(request, "O título do card não pode ficar vazio.")
                return redirect("questions:card_editar", pk=pk)
            card.title = titulo[:200]
            card.is_published = request.POST.get("is_published") == "on"
            card.save()

            ultima_ordem = 0
            for b in card.bullets.all():
                texto = request.POST.get(f"bullet-{b.id}", b.text).strip()
                if request.POST.get(f"remover-{b.id}") == "on" or not texto:
                    b.delete()
                    continue
                if texto != b.text:
                    b.text = texto
                    b.save(update_fields=["text"])
                ultima_ordem = max(ultima_ordem, b.order)
            novo = request.POST.get("novo", "").strip()
            if novo:
                RuleBullet.objects.create(card=card, text=novo, order=ultima_ordem + 1)

            depois = _snapshot(card)
            if depois != antes:
                CardRevision.objects.create(
                    card=card,
                    card_label=f"{card.rule.title} › {card.title}"[:420],
                    user=request.user,
                    user_label=_rotulo_usuario(request.user)[:254],
                    before=antes,
                    after=depois,
                )
                messages.success(request, "Card salvo. A alteração ficou registrada no histórico.")
            else:
                messages.info(request, "Nada mudou.")
        return redirect("questions:card_editar", pk=pk)

    snap = _snapshot(card)
    return render(request, "questions/painel_card.html", {
        "card": card,
        "bullets": card.bullets.order_by("order", "id"),
        "versao": _versao(snap),
        "revisoes": [_com_mudancas(r) for r in card.revisions.all()[:10]],
    })


# --- Histórico -----------------------------------------------------------------

def _mudancas(antes: dict, depois: dict) -> list[dict]:
    out = []
    if antes["title"] != depois["title"]:
        out.append({"tipo": "Título", "de": antes["title"], "para": depois["title"]})
    if antes["is_published"] != depois["is_published"]:
        simnao = {True: "publicado", False: "oculto"}
        out.append({"tipo": "Publicação", "de": simnao[antes["is_published"]], "para": simnao[depois["is_published"]]})
    a = {b["id"]: b["text"] for b in antes["bullets"]}
    d = {b["id"]: b["text"] for b in depois["bullets"]}
    for bid, texto in a.items():
        if bid not in d:
            out.append({"tipo": "Item removido", "de": texto, "para": ""})
        elif d[bid] != texto:
            out.append({"tipo": "Item alterado", "de": texto, "para": d[bid]})
    for bid, texto in d.items():
        if bid not in a:
            out.append({"tipo": "Item adicionado", "de": "", "para": texto})
    return out


def _com_mudancas(rev):
    rev.mudancas = _mudancas(rev.before, rev.after)
    return rev


@staff_required
def historico(request):
    qs = CardRevision.objects.select_related("card")
    quem = request.GET.get("quem", "").strip()
    if quem:
        qs = qs.filter(user_label__icontains=quem)
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    page_obj.object_list = [_com_mudancas(r) for r in page_obj.object_list]
    return render(request, "questions/painel_historico.html", {"page_obj": page_obj, "quem": quem})
