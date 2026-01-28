---
category: Manual 2026
category_slug: manual-2026
# Opcional: versão/fonte
source: "Manual SAMU 192 (43 páginas)"
---

# Como editar este arquivo

## Estrutura (o que vira o quê)

- `## ...` vira uma **Rule** (capítulo/subtema principal no site)
- `### ...` vira um **RuleCard** dentro da Rule
- Linhas de lista `- ...` (ou `1. ...`) viram **RuleBullet**
- Texto “solto” (parágrafos) dentro de um card também vira bullet (para não perder nada)

## Tags (para melhorar busca)

As tags são opcionais, mas ajudam muito na busca. Elas são aplicadas **por bullet**.

### Definir tags (opcional)

Você pode declarar tags no topo ou em qualquer lugar:

- `@tag comunicacao:telegram = Telegram`
- `@tag seguranca:epi = EPI`
- `@tag operacional:plantao = Plantão`

Formato:
- `@tag <kind>:<slug> = <Nome>`
- `kind` (opcional) pode ser: `processo`, `seguranca`, `comunicacao`, `juridico`, `operacional`, `outros`
- Se você omitir `kind:`, o script assume `outros`.

### Aplicar tags aos próximos bullets

Use uma linha de diretiva:

- `@tags: seguranca:epi, comunicacao:telegram, plantao`

Isso aplica essas tags em todos os bullets seguintes **até** outra linha `@tags:` ou um novo heading.

### Aplicar tags em um bullet específico

Você também pode aplicar tags inline:

- `- [tags: seguranca:epi, comunicacao:telegram] Texto do bullet...`

(As tags inline somam com as tags ativas do bloco.)

---

## 0. Apresentação

### Geral
@tags: outros:introducao
- Cole aqui o texto da apresentação.
- Pode quebrar em vários bullets sem resumir.

## 1. ROTINAS NA REGULAÇÃO

### 1.1. EQUIPE MÉDICA REGULAÇÃO
@tags: operacional:regulacao
- (Cole os bullets aqui)

### 1.2. CHEFIA DE PLANTÃO
@tags: operacional:plantao
- (Cole a introdução da seção aqui)

### 1.2.1. (subitem)
@tags: operacional:plantao
- (Cole os bullets do 1.2.1)

### 1.2.2. (subitem)
- (Cole os bullets do 1.2.2)

### 1.3. CHEGADAS E SAÍDAS - CRU
- ...

## 2. PROTOCOLOS OPERACIONAIS DA CENTRAL DE REGULAÇÃO DAS URGÊNCIAS – CRU

### 2.1. OCORRÊNCIAS
- ...

## 3. ROTINAS NA INTERVENÇÃO

### 3.1. CHEGADAS E SAÍDAS INTERVENÇÃO
- ...

## 4. PROTOCOLOS ESPECIAIS INTERVENÇÃO

### 4.1. APOIO A UNIDADE DE SUPORTE BÁSICO
- ...

## 5. ORIENTAÇÕES GERAIS

### 5.1. PONTUALIDADE E ASSIDUIDADE
- ...

## 6. ROTINA PARA ACIONAMENTO DA COMISSÃO DE ÉTICA MÉDICA

### Geral
- ...

## 7. RESPOSTAS ÀS PERGUNTAS FREQUENTES

### Geral
- ...

## 8. ANEXOS

### Geral
- ...
