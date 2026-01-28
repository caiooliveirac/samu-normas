#!/usr/bin/env python3
"""Converte um PDF (manual) em um rules_seed.json no formato do comando seed_rules.

Objetivo: acelerar a criação do dataset inicial para o site (cards/bullets) a partir
de um documento PDF. O resultado é um *rascunho estruturado* que normalmente precisa
de revisão humana (principalmente títulos e quebra de seções).

Uso:
  . .venv/bin/activate
  python scripts/pdf_manual_to_rules_seed.py \
    --pdf docs/Manual_SAMU_192_FINAL.pdf \
    --out rules_seed.json

Regras de parsing (heurísticas):
- Remove cabeçalhos/rodapés comuns.
- Detecta títulos por padrões (CAPÍTULO, Seção numerada, linhas em caixa alta).
- Cria:
  - 1 Category: "Manual 2026"
  - Rules = seções principais
  - Cards = subseções
  - Bullets = linhas/itens/parágrafos dentro de cada card

"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader


HEADER_FOOTER_HINTS: list[str] = []


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\u00e0-\u00ff\s-]", "", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-") or "secao"


def normalize_line(line: str) -> str:
    line = line.replace("\u00a0", " ")
    line = re.sub(r"\s+", " ", line)
    return line.strip()


def is_noise(line: str) -> bool:
    if not line:
        return True
    if len(line) <= 2 and line.isdigit():
        return True
    # Ex: "2026 2" / "2026 10" etc.
    if re.fullmatch(r"\d{4}\s+\d+", line):
        return True
    return False


TOC_LINE_RE = re.compile(r"^(?P<num>\d+(?:\.\d+)*)\.\s+(?P<title>.+)$")
SUBHEADING_RE = re.compile(r"^(?:[-\u2022]\s*)?(?P<num>\d+(?:\.\d+)+)\.\s+(?P<title>.+)$")


STOPWORDS = {
    "A",
    "AS",
    "AO",
    "AOS",
    "À",
    "ÀS",
    "O",
    "OS",
    "UM",
    "UMA",
    "UNS",
    "UMAS",
    "DE",
    "DA",
    "DO",
    "DAS",
    "DOS",
    "E",
    "EM",
    "NO",
    "NA",
    "NOS",
    "NAS",
    "PARA",
    "POR",
    "COM",
    "SEM",
    "SOBRE",
}


def title_tokens(title: str) -> set[str]:
    t = normalize_match(title)
    toks = re.findall(r"[A-ZÀ-ÖØ-Ý]{3,}", t)
    return {w for w in toks if w not in STOPWORDS}


def normalize_match(s: str) -> str:
    s = normalize_line(s)
    s = s.replace("–", "-")
    s = re.sub(r"\s+", " ", s)
    return s.strip().upper()


def is_all_caps(line: str) -> bool:
    letters = re.sub(r"[^A-Za-z\u00c0-\u00ff]", "", line)
    if len(letters) < 5:
        return False
    upper_letters = sum(1 for c in letters if c.isupper())
    return (upper_letters / max(1, len(letters))) > 0.9


@dataclass
class Card:
    title: str
    bullets: list[str] = field(default_factory=list)


@dataclass
class RuleSection:
    title: str
    cards: list[Card] = field(default_factory=list)


def extract_lines(reader: PdfReader) -> list[str]:
    # Primeiro passo: coletar linhas por página (sem remover cabeçalho/rodapé ainda)
    pages: list[list[str]] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        page_lines: list[str] = []
        for raw in text.splitlines():
            line = normalize_line(raw)
            if not line:
                continue
            page_lines.append(line)
        pages.append(page_lines)

    # Segundo passo: detectar cabeçalhos/rodapés por repetição entre páginas.
    # Regra reprodutível: linhas curtas que se repetem em várias páginas tendem a ser ruído.
    from collections import Counter

    counts = Counter()
    for page_lines in pages:
        # conta presença por página (não frequência dentro da página)
        for l in set(page_lines):
            key = normalize_match(l)
            if not key:
                continue
            # evita considerar headings como ruído
            if TOC_LINE_RE.match(l) or SUBHEADING_RE.match(l):
                continue
            counts[key] += 1

    # threshold: aparece em >=3 páginas e é relativamente curto
    repeated_noise = {k for k, c in counts.items() if c >= 3 and len(k) <= 120}

    # Terceiro passo: montar lista final com filtros genéricos + repetição
    lines: list[str] = []
    for page_lines in pages:
        for raw in page_lines:
            if is_noise(raw):
                continue
            if normalize_match(raw) in repeated_noise:
                continue
            lines.append(raw)
        lines.append("")
    return lines


@dataclass
class TocEntry:
    num: str
    title: str


def parse_toc(lines: list[str]) -> list[TocEntry]:
    """Extrai o SUMÁRIO do texto.

    O PDF costuma quebrar títulos longos em múltiplas linhas; juntamos linhas
    em caixa alta como continuação do item anterior.
    """
    try:
        start = next(i for i, l in enumerate(lines) if normalize_match(l) == "SUMÁRIO")
    except StopIteration:
        return []

    toc_end = find_toc_end_index(lines) or min(len(lines), start + 500)
    entries: list[TocEntry] = []
    for raw in lines[start + 1 : toc_end]:
        line = raw.strip()
        if not line:
            continue
        m = TOC_LINE_RE.match(line)
        if m:
            num = m.group("num")
            title = m.group("title").strip()
            # remove possível número de página no final
            title = re.sub(r"\s+\d{1,3}$", "", title).strip()
            entries.append(TocEntry(num=num, title=title))
            continue

        # Continuação do título anterior (o PDF quebra em múltiplas linhas, nem sempre caps)
        if entries and not TOC_LINE_RE.match(line):
            # Evita colar lixo óbvio
            if is_noise(line):
                continue
            # remove número de página solto
            cont = re.sub(r"\s+\d{1,3}$", "", line).strip()
            if cont:
                entries[-1].title = (entries[-1].title + " " + cont).strip()

    # Normaliza títulos
    for e in entries:
        e.title = normalize_line(e.title)
    # Dedup por num (alguns PDFs repetem blocos do sumário em quebras)
    seen: set[str] = set()
    deduped: list[TocEntry] = []
    for e in entries:
        if e.num in seen:
            continue
        seen.add(e.num)
        deduped.append(e)
    return deduped


LEADING_NUM_RE = re.compile(r"^(?P<num>\d+(?:\.\d+)*)(?:\.)?(?:\s+|$)")


def leading_section_number(line: str) -> str | None:
    """Extrai o número de seção do começo de uma linha.

    Ex:
      "1. ROTINAS ..." -> "1"
      "1.6. REGULAÇÃO ..." -> "1.6"
      "1.1 EQUIPE ..." -> "1.1"
    """
    if not line:
        return None
    m = LEADING_NUM_RE.match(normalize_line(line))
    if not m:
        return None
    num = m.group("num")
    # Evita capturar anos soltos como "2026" em cabeçalhos (já filtrados, mas por segurança)
    if len(num) == 4 and num.isdigit() and num.startswith("20"):
        return None
    return num


def normalize_num(n: str) -> str:
    # Trata 7 e 7.0 como equivalentes para matching de âncoras.
    while n.endswith(".0"):
        n = n[: -2]
    return n


def find_toc_end_index(lines: list[str]) -> int | None:
    """Retorna o índice logo após o bloco do SUMÁRIO para começar a busca no corpo."""
    try:
        start = next(i for i, l in enumerate(lines) if normalize_match(l) == "SUMÁRIO")
    except StopIteration:
        return None

    entries_seen = False
    max_top_seen = 0
    i = start + 1
    max_scan = min(len(lines), start + 500)
    while i < max_scan:
        line = lines[i]
        if not line:
            i += 1
            continue
        if TOC_LINE_RE.match(line):
            entries_seen = True
            num = leading_section_number(line)
            if num:
                try:
                    top = int(num.split(".", 1)[0])
                except ValueError:
                    top = 0
                if top:
                    # No SUMÁRIO a numeração sobe (1..9). No corpo, ela costuma reiniciar em 1.
                    # Se já vimos capítulos altos e voltamos para 1, consideramos fim do SUMÁRIO.
                    if max_top_seen >= 5 and top == 1:
                        break
                    max_top_seen = max(max_top_seen, top)
            i += 1
            continue
        if entries_seen and is_all_caps(line) and not TOC_LINE_RE.match(line):
            i += 1
            continue
        if entries_seen:
            break
        i += 1
    return i


def find_anchor_index(lines: list[str], num: str, title: str, *, start_at: int = 0) -> int | None:
    """Encontra a linha de início de uma seção no corpo do PDF.

    Preferência: casar por num + título (normalizado). Fallback: casar só pelo num.
    """
    want_full = normalize_match(f"{num}. {title}")

    # 1) Match bem estrito: linha igual/começando com "num. título".
    want_num_norm = normalize_num(num)

    for idx in range(start_at, len(lines)):
        raw = lines[idx]
        if not raw:
            continue
        got_num = leading_section_number(raw)
        if not got_num or normalize_num(got_num) != want_num_norm:
            continue
        got = normalize_match(raw)
        if got == want_full or got.startswith(want_full):
            return idx

    # 2) Match “inteligente”: linha começa com num, e o texto (ou a próxima linha) tem tokens do título.
    want_tokens = title_tokens(title)
    level = num.count(".") + 1
    min_hits = 2
    if len(want_tokens) <= 2:
        min_hits = 1
    if level == 1:
        min_hits = 1

    best_idx: int | None = None
    best_score = -1

    for idx in range(start_at, len(lines)):
        raw = lines[idx]
        if not raw:
            continue
        got = normalize_match(raw)
        got_num = leading_section_number(raw)
        if not got_num or normalize_num(got_num) != want_num_norm:
            continue

        # Evita confundir headings com itens de lista tipo "1)" ou "1." isolado com texto de lista.
        if re.match(r"^\d+(?:\.\d+)*\)\s+", raw):
            continue

        candidate = raw
        # Se a próxima linha parece continuação do heading (muito comum no PDF), inclui pra pontuar.
        if idx + 1 < len(lines):
            nxt = lines[idx + 1]
            if nxt and not TOC_LINE_RE.match(nxt) and is_all_caps(nxt):
                candidate = f"{raw} {nxt}"

        cand_tokens = title_tokens(candidate)
        hits = len(cand_tokens & want_tokens) if want_tokens else 0

        # Heurística adicional: heading costuma ser caps; isso desempata.
        bonus = 1 if is_all_caps(raw) else 0
        score = hits * 10 + bonus

        if hits >= min_hits and score > best_score:
            best_score = score
            best_idx = idx

    if best_idx is not None:
        return best_idx

    # 3) Fallback MUITO conservador (só para nível 1): evita falso positivo em níveis profundos.
    if level == 1:
        for idx in range(start_at, len(lines)):
            raw = lines[idx]
            if not raw:
                continue
            got_num = leading_section_number(raw)
            if not got_num or normalize_num(got_num) != want_num_norm:
                continue
            got = normalize_match(raw)
            if got:
                # Só aceita se parece heading de verdade.
                if is_all_caps(raw) or len(raw) <= len(num) + 3:
                    return idx

    return None


def split_body_by_toc(lines: list[str], toc: list[TocEntry], *, body_start: int = 0) -> list[tuple[TocEntry, list[str]]]:
    """Divide o corpo do documento em blocos por item do sumário."""
    if not toc:
        return []

    # Encontra âncoras no corpo
    anchors: list[tuple[int, TocEntry]] = []
    for entry in toc:
        idx = find_anchor_index(lines, entry.num, entry.title, start_at=body_start)
        if idx is not None:
            anchors.append((idx, entry))

    anchors.sort(key=lambda t: t[0])
    if not anchors:
        return []

    chunks: list[tuple[TocEntry, list[str]]] = []
    for (start_idx, entry), (end_idx, _) in zip(anchors, anchors[1:] + [(len(lines), anchors[-1][1])]):
        block = lines[start_idx:end_idx]
        chunks.append((entry, block))
    return chunks


def build_sections(lines: list[str]) -> list[RuleSection]:
    toc = parse_toc(lines)
    toc_end = find_toc_end_index(lines) or 0
    chunks = split_body_by_toc(lines, toc, body_start=toc_end)
    if not chunks:
        # Fallback: pelo menos um "bucket" único
        return [RuleSection(title="Manual 2026", cards=[Card(title="Geral", bullets=[l for l in lines if l])])]

    # Prefácio (conteúdo antes do SUMÁRIO)
    preface_sections: list[RuleSection] = []
    try:
        toc_start = next(i for i, l in enumerate(lines) if normalize_match(l) == "SUMÁRIO")
    except StopIteration:
        toc_start = 0

    preface_lines = [l for l in lines[:toc_start] if l and not is_noise(l)]
    if preface_lines:
        bullets: list[str] = []
        pending: list[str] = []

        def flush_preface():
            nonlocal pending
            if not pending:
                return
            paragraph = " ".join(pending).strip()
            pending = []
            if paragraph:
                bullets.append(paragraph)

        for l in preface_lines:
            if not l:
                flush_preface()
                continue
            pending.append(l)
        flush_preface()

        if bullets:
            preface_sections.append(RuleSection(title="0. Apresentação", cards=[Card(title="Geral", bullets=bullets)]))

    sections_by_top: dict[str, RuleSection] = {}

    def split_long_text(text: str, *, max_len: int = 420) -> list[str]:
        """Divide um texto longo em pedaços menores sem resumir.

        Estratégia:
        - Primeiro tenta quebrar em sentenças (.?!).
        - Se ainda ficar grande, quebra por ';' ou ':'
        - Se ainda ficar grande, quebra por tamanho (hard wrap) preservando tudo.
        """

        t = normalize_line(text)
        if not t:
            return []
        if len(t) <= max_len:
            return [t]

        parts: list[str] = []

        # Sentenças
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", t) if s.strip()]
        if len(sentences) > 1:
            buf = ""
            for s in sentences:
                if not buf:
                    buf = s
                    continue
                if len(buf) + 1 + len(s) <= max_len:
                    buf = f"{buf} {s}"
                else:
                    parts.append(buf)
                    buf = s
            if buf:
                parts.append(buf)
        else:
            parts = [t]

        # Segunda passada: ainda grande? tenta por ';' / ':'
        refined: list[str] = []
        for p in parts:
            if len(p) <= max_len:
                refined.append(p)
                continue
            chunks = [c.strip() for c in re.split(r"\s*[;:]\s+", p) if c.strip()]
            if len(chunks) > 1:
                refined.extend(chunks)
            else:
                refined.append(p)

        # Hard wrap final (último recurso)
        final: list[str] = []
        for p in refined:
            if len(p) <= max_len:
                final.append(p)
                continue
            start = 0
            while start < len(p):
                end = min(len(p), start + max_len)
                # tenta cortar em espaço
                if end < len(p):
                    space = p.rfind(" ", start, end)
                    if space > start + 40:
                        end = space
                final.append(p[start:end].strip())
                start = end
        return [x for x in final if x]

    def add_bullet(card: Card, text: str) -> None:
        for piece in split_long_text(text):
            if piece:
                card.bullets.append(piece)

    def get_top_key(num: str) -> str:
        return num.split(".", 1)[0]

    def top_rule_title(top_num: str) -> str:
        for e in toc:
            if e.num == top_num:
                return f"{e.num}. {e.title}"
        return f"{top_num}."

    for entry, block in chunks:
        top_num = get_top_key(entry.num)
        rule = sections_by_top.get(top_num)
        if rule is None:
            rule = RuleSection(title=top_rule_title(top_num), cards=[])
            sections_by_top[top_num] = rule

        # Decide card title: o próprio item do toc para níveis >=2, senão "Geral"
        level = entry.num.count(".") + 1
        card_title = "Geral" if level == 1 else f"{entry.num}. {entry.title}"
        base_card = Card(title=card_title, bullets=[])
        cards_to_add: list[Card] = [base_card]
        current_card = base_card

        # Remove a primeira linha se ela for o próprio heading
        cleaned_block: list[str] = []
        for i, l in enumerate(block):
            if i == 0 and normalize_match(l).startswith(normalize_match(f"{entry.num}.")):
                continue
            if is_noise(l):
                continue
            cleaned_block.append(l)

        # Quebra em parágrafos/bullets
        pending: list[str] = []

        def flush():
            nonlocal pending
            if not pending:
                return
            paragraph = " ".join(pending).strip()
            pending = []
            if paragraph:
                add_bullet(current_card, paragraph)

        def should_join(prev: str, cur: str) -> bool:
            """Heurística para juntar linhas quebradas pelo PDF.

            Em geral: junta quando a linha anterior não termina uma frase.
            """
            if not prev:
                return False
            if prev.endswith("-") and cur and cur[0].islower():
                return True
            if prev.endswith((".", "!", "?")):
                return False
            # Ex: títulos ou início forte de item
            if re.match(r"^(?:\d+\)|\d+\.|[a-zA-Z]\))\s+", cur):
                return False
            if is_all_caps(cur):
                return False
            return True

        def start_new_card(title: str) -> None:
            nonlocal current_card
            current_card = Card(title=title, bullets=[])
            cards_to_add.append(current_card)

        i = 0
        while i < len(cleaned_block):
            l = cleaned_block[i]
            if not l:
                flush()
                i += 1
                continue

            # Detecta sub-seções numeradas dentro da seção atual (ex.: 1.2.1.)
            m_sub = SUBHEADING_RE.match(l)
            if m_sub:
                sub_num = m_sub.group("num")
                sub_title = normalize_line(m_sub.group("title"))
                # Só vale se for descendente do entry atual (evita pegar numeração de outros capítulos)
                if sub_num.startswith(f"{entry.num}."):
                    flush()
                    # Card com título curto (apenas numeração) e texto completo como primeira bullet.
                    start_new_card(f"{sub_num}")
                    if sub_title:
                        add_bullet(current_card, sub_title)
                    i += 1
                    continue

            if re.match(r"^[-\u2022]\s+", l):
                flush()
                bullet = re.sub(r"^[-\u2022]\s+", "", l).strip()
                if bullet:
                    add_bullet(current_card, bullet)
                i += 1
                continue
            # Listas numeradas simples (1), 1., a), etc.
            if re.match(r"^(?:\d+\)|\d+\.|[a-zA-Z]\))\s+", l):
                flush()
                add_bullet(current_card, l)
                i += 1
                continue
            if pending and should_join(pending[-1], l):
                pending[-1] = (pending[-1].rstrip("-") + ("" if pending[-1].endswith("-") else " ") + l).strip()
            else:
                flush()
                pending.append(l)
            i += 1
        flush()

        # Adiciona cards que tiverem conteúdo; se o card base ficou vazio, ignora.
        for c in cards_to_add:
            if any(b.strip() for b in c.bullets):
                rule.cards.append(c)

    # Ordena rules pelo número
    ordered = [sections_by_top[k] for k in sorted(sections_by_top.keys(), key=lambda x: int(x) if x.isdigit() else 9999)]
    # Remove rules sem cards
    ordered = [r for r in ordered if r.cards]
    return preface_sections + ordered


def to_fixture(sections: list[RuleSection]) -> list[dict]:
    fixture: list[dict] = []

    # Category única
    fixture.append(
        {
            "model": "questions.category",
            "pk": 1,
            "fields": {"name": "Manual 2026", "slug": "manual-2026"},
        }
    )

    rule_pk = 1000
    card_pk = 10000
    bullet_pk = 100000

    used_rule_slugs: set[str] = set()

    def unique_rule_slug(title: str) -> str:
        base = slugify(title)
        # Rule.slug (models.SlugField sem max_length) usa default 50
        base = base[:50] if base else "secao"
        candidate = base
        n = 2
        while candidate in used_rule_slugs:
            suffix = f"-{n}"
            candidate = (base[: (50 - len(suffix))] + suffix).strip("-")
            n += 1
        used_rule_slugs.add(candidate)
        return candidate

    for idx, sec in enumerate(sections, start=1):
        rule_pk += 1
        rule_slug = unique_rule_slug(sec.title)
        fixture.append(
            {
                "model": "questions.rule",
                "pk": rule_pk,
                "fields": {
                    "title": sec.title[:200],
                    "slug": rule_slug,
                    "category": 1,
                    "is_published": True,
                    "order": idx * 10,
                    "body": "",
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                },
            }
        )

        for c_idx, card in enumerate(sec.cards, start=1):
            card_pk += 1
            fixture.append(
                {
                    "model": "questions.rulecard",
                    "pk": card_pk,
                    "fields": {
                        "rule": rule_pk,
                        "title": (card.title or "Geral")[:200],
                        "order": c_idx,
                        "is_published": True,
                    },
                }
            )

            for b_idx, bullet in enumerate(card.bullets, start=1):
                text = bullet.strip()
                if not text:
                    continue
                bullet_pk += 1
                fixture.append(
                    {
                        "model": "questions.rulebullet",
                        "pk": bullet_pk,
                        "fields": {
                            "card": card_pk,
                            "text": text,
                            "order": b_idx,
                            "tags": [],
                        },
                    }
                )

    return fixture


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, help="Caminho do PDF")
    ap.add_argument("--out", required=True, help="Arquivo JSON de saída (rules_seed.json)")
    ap.add_argument("--dump-text", action="store_true", help="Também salva o texto extraído em .txt ao lado do out")
    ap.add_argument(
        "--audit-anchors",
        action="store_true",
        help="Imprime auditoria do SUMÁRIO vs âncoras encontradas no corpo (diagnóstico)",
    )
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.is_file():
        raise SystemExit(f"PDF não encontrado: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    lines = extract_lines(reader)

    if args.audit_anchors:
        toc = parse_toc(lines)
        toc_end = find_toc_end_index(lines) or 0
        found = 0
        print("AUDITORIA ÂNCORAS (SUMÁRIO -> corpo)")
        for e in toc:
            idx = find_anchor_index(lines, e.num, e.title, start_at=toc_end)
            ok = idx is not None
            found += 1 if ok else 0
            sample = ""
            if idx is not None:
                sample = normalize_line(lines[idx])
            status = "OK" if ok else "MISS"
            print(f"{status:4} {e.num:8} {e.title[:70]:70} | {sample[:70]}")
        print(f"Encontradas: {found}/{len(toc)}")
    sections = build_sections(lines)

    fixture = to_fixture(sections)
    out_path = Path(args.out)
    out_path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.dump_text:
        txt_path = out_path.with_suffix(".extracted.txt")
        txt_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"OK: gerado {out_path} ({len(fixture)} objetos; {len(sections)} regras)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
