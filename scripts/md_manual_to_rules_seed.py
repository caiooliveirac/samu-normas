#!/usr/bin/env python3
"""Converte um manual em Markdown para rules_seed.json (fixture para seed_rules).

Objetivo: substituir parsing de PDF por um formato fonte controlável (Markdown),
com estrutura determinística e tags opcionais.

Convenções:
- '## Título' -> Rule
- '### Título' -> RuleCard
- Bullets '- ' / '* ' / '1. ' -> RuleBullet
- Texto solto dentro de um card vira bullet (para não perder conteúdo)

Tags:
- Definição opcional: '@tag kind:slug = Nome'
- Tags ativas no bloco: '@tags: kind:slug, outra'
- Tags inline no bullet: '- [tags: a, b] texto'

Front matter (opcional, YAML simples):
---
category: Manual 2026
category_slug: manual-2026
---

Uso:
  . .venv/bin/activate
  python scripts/md_manual_to_rules_seed.py --md docs/manual.md --out rules_seed.json

"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


KIND_CHOICES = {"processo", "seguranca", "comunicacao", "juridico", "operacional", "outros"}


def slugify(value: str) -> str:
    v = value.strip().lower()
    v = re.sub(r"[^a-z0-9\u00e0-\u00ff\s-]", "", v)
    v = re.sub(r"\s+", "-", v)
    v = re.sub(r"-+", "-", v)
    return v.strip("-") or "tag"


def normalize_line(s: str) -> str:
    s = s.replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def parse_front_matter(lines: list[str]) -> tuple[dict, int]:
    if not lines or lines[0].strip() != "---":
        return {}, 0
    fm: dict[str, str] = {}
    i = 1
    while i < len(lines):
        line = lines[i].rstrip("\n")
        if line.strip() == "---":
            return fm, i + 1
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"')
        i += 1
    return fm, 0


HEADING_RE = re.compile(r"^(?P<lvl>#{2,3})\s+(?P<title>.+?)\s*$")
TAG_DEF_RE = re.compile(r"^@tag\s+(?P<spec>[^=]+?)\s*=\s*(?P<name>.+?)\s*$")
TAGS_LINE_RE = re.compile(r"^@tags:\s*(?P<list>.+?)\s*$")
INLINE_TAGS_RE = re.compile(r"^\[tags:\s*(?P<list>[^\]]+)\]\s*(?P<rest>.*)$", re.IGNORECASE)
BULLET_RE = re.compile(r"^(?:[-*]|\d+\.)\s+(?P<text>.+)$")


def parse_tag_spec(spec: str) -> tuple[str, str]:
    """Retorna (kind, slug). kind pode ser 'outros'."""
    spec = normalize_line(spec)
    if ":" in spec:
        kind, slug = spec.split(":", 1)
        kind = kind.strip().lower()
        slug = slugify(slug)
        if kind not in KIND_CHOICES:
            kind = "outros"
        return kind, slug
    return "outros", slugify(spec)


@dataclass
class TagInfo:
    kind: str
    slug: str
    name: str
    pk: int


@dataclass
class Bullet:
    text: str
    tag_specs: list[str] = field(default_factory=list)


@dataclass
class Card:
    title: str
    bullets: list[Bullet] = field(default_factory=list)


@dataclass
class Rule:
    title: str
    cards: list[Card] = field(default_factory=list)


def md_to_structure(md_text: str) -> tuple[dict, list[Rule], dict[str, tuple[str, str]]]:
    lines = md_text.splitlines(True)
    fm, start = parse_front_matter(lines)

    tag_defs: dict[str, tuple[str, str]] = {}
    rules: list[Rule] = []
    current_rule: Rule | None = None
    current_card: Card | None = None
    active_tags: list[str] = []
    started_rules = False

    def ensure_rule(title: str) -> Rule:
        nonlocal current_rule, current_card
        r = Rule(title=normalize_line(title))
        rules.append(r)
        current_rule = r
        current_card = None
        return r

    def ensure_card(title: str) -> Card:
        nonlocal current_card
        if current_rule is None:
            ensure_rule("Geral")
        c = Card(title=normalize_line(title))
        current_rule.cards.append(c)
        current_card = c
        return c

    def add_bullet(text: str, tags: list[str]):
        if current_card is None:
            ensure_card("Geral")
        t = normalize_line(text)
        if not t:
            return
        current_card.bullets.append(Bullet(text=t, tag_specs=list(tags)))

    in_code = False
    for raw in lines[start:]:
        line = raw.rstrip("\n")

        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue

        stripped = line.strip()
        if not stripped:
            continue

        m_def = TAG_DEF_RE.match(stripped)
        if m_def:
            kind, slug = parse_tag_spec(m_def.group("spec"))
            name = normalize_line(m_def.group("name")).strip('"')
            tag_defs[slug] = (name, kind)
            continue

        m_tags = TAGS_LINE_RE.match(stripped)
        if m_tags:
            specs = [normalize_line(x) for x in m_tags.group("list").split(",")]
            active_tags = [x for x in specs if x]
            continue

        m_head = HEADING_RE.match(stripped)
        if m_head:
            lvl = m_head.group("lvl")
            title = m_head.group("title")
            if lvl == "##":
                started_rules = True
                ensure_rule(title)
            else:
                ensure_card(title)
            active_tags = []
            continue

        # Ignora qualquer conteúdo antes do primeiro '##'. Isso evita que notas
        # introdutórias (ex.: '# Draft', '> ...') virem bullets em um card 'Geral'.
        if not started_rules:
            continue

        m_b = BULLET_RE.match(stripped)
        if m_b:
            text = m_b.group("text")
            inline_tags = []
            m_in = INLINE_TAGS_RE.match(text.strip())
            if m_in:
                inline_tags = [normalize_line(x) for x in m_in.group("list").split(",") if normalize_line(x)]
                text = m_in.group("rest")
            add_bullet(text, active_tags + inline_tags)
            continue

        # Texto solto: vira bullet
        add_bullet(stripped, active_tags)

    return fm, rules, tag_defs


def unique_slug(base: str, used: set[str], *, max_len: int) -> str:
    b = slugify(base)[:max_len] or "secao"
    candidate = b
    n = 2
    while candidate in used:
        suffix = f"-{n}"
        candidate = (b[: (max_len - len(suffix))] + suffix).strip("-")
        n += 1
    used.add(candidate)
    return candidate


def build_fixture(fm: dict, rules: list[Rule], tag_defs: dict[str, tuple[str, str]]):
    category_name = fm.get("category") or "Manual"
    category_slug = fm.get("category_slug") or unique_slug(category_name, set(), max_len=140)

    fixture: list[dict] = []
    fixture.append({"model": "questions.category", "pk": 1, "fields": {"name": category_name, "slug": category_slug}})

    # Tags: criadas sob demanda conforme usadas
    tag_pk = 10
    tag_by_slug: dict[str, TagInfo] = {}

    def ensure_tag(spec: str) -> int:
        nonlocal tag_pk
        kind, slug = parse_tag_spec(spec)
        if slug in tag_by_slug:
            return tag_by_slug[slug].pk
        name, kind2 = tag_defs.get(slug, (slug.replace("-", " ").title(), kind))
        if kind2 in KIND_CHOICES:
            kind = kind2
        tag_pk += 1
        tag_by_slug[slug] = TagInfo(kind=kind, slug=slug, name=name, pk=tag_pk)
        fixture.append({
            "model": "questions.tag",
            "pk": tag_pk,
            "fields": {"name": name[:64], "slug": slug[:80], "kind": kind},
        })
        return tag_pk

    used_rule_slugs: set[str] = set()
    rule_pk = 1000
    card_pk = 10000
    bullet_pk = 100000

    for r_idx, rule in enumerate(rules, start=1):
        rule_pk += 1
        rule_slug = unique_slug(rule.title, used_rule_slugs, max_len=50)
        fixture.append({
            "model": "questions.rule",
            "pk": rule_pk,
            "fields": {
                "title": rule.title[:200],
                "slug": rule_slug,
                "category": 1,
                "is_published": True,
                "order": r_idx * 10,
                "body": "",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            },
        })

        for c_idx, card in enumerate(rule.cards, start=1):
            card_pk += 1
            fixture.append({
                "model": "questions.rulecard",
                "pk": card_pk,
                "fields": {"rule": rule_pk, "title": (card.title or "Geral")[:200], "order": c_idx, "is_published": True},
            })

            for b_idx, bullet in enumerate(card.bullets, start=1):
                text = bullet.text.strip()
                if not text:
                    continue
                bullet_pk += 1
                tag_ids = []
                for spec in bullet.tag_specs:
                    if spec:
                        tag_ids.append(ensure_tag(spec))
                fixture.append({
                    "model": "questions.rulebullet",
                    "pk": bullet_pk,
                    "fields": {"card": card_pk, "text": text, "order": b_idx, "tags": tag_ids},
                })

    return fixture


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", required=True, help="Arquivo Markdown fonte (ex.: docs/manual.md)")
    ap.add_argument("--out", required=True, help="Saída JSON (rules_seed.json)")
    args = ap.parse_args()

    md_path = Path(args.md)
    if not md_path.is_file():
        raise SystemExit(f"Markdown não encontrado: {md_path}")

    fm, rules, tag_defs = md_to_structure(md_path.read_text(encoding="utf-8"))
    fixture = build_fixture(fm, rules, tag_defs)

    out_path = Path(args.out)
    out_path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: gerado {out_path} ({len(fixture)} objetos; rules={len([x for x in fixture if x['model']=='questions.rule'])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
