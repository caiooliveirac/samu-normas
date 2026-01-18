# Checklists USA + Digest no Telegram

Este documento descreve o fluxo de checklists da USA no projeto e como funciona o envio de um resumo (“digest”) no Telegram.

## Visão geral

- Página de preenchimento: `/checklists/`
- API de envio do checklist: `POST /api/checklists/submit/`
- Inbox (staff) para visualizar envios: `/inbox/checklists/`
- API (staff) para enviar digest no Telegram: `POST /api/checklists/digest/send/`

O digest lista:

1) Quais ambulâncias esperadas **não enviaram** checklist no dia.
2) Para as que enviaram, quais itens foram sinalizados como **faltando** e quais **observações** foram registradas.

## Arquivos base do checklist

O checklist é definido em Markdown e usado tanto na UI de preenchimento quanto no “compactador” de rótulos do Telegram.

- `docs/checklist.md`: checklist completo (fonte de verdade)
- `docs/checklist_compact.md`: opcional; rótulos curtos na **mesma ordem** e com a **mesma quantidade** de itens

Se `checklist_compact.md` não existir (ou estiver fora de sincronia), o sistema cai para heurísticas automáticas para encurtar os itens.

## Formato do texto salvo

O backend não interpreta checkbox por checkbox na submissão; ele recebe e salva um **texto final**.

Para o digest funcionar bem, o texto costuma conter linhas no padrão:

- Itens faltando: começam com `🚫`.
- Observações: trecho `— Obs:` na mesma linha do item.

Exemplos:

- `🚫 LARINGOSCÓPIO ADULTO — Obs: lâmina 3 no almox`
- `✅ DEA — Obs: bateria 90%`

## Normalização de unidade (SM01 etc.)

O digest considera uma lista fixa de unidades esperadas e faz normalização tolerante do campo `unit`.

- Aceita variações como `SM 01`, `SM-01`.
- Em alguns casos, também tolera `SM1` e converte para `SM01`.

## Telegram (configuração)

Configurar no ambiente (ex.: `.env.prod`) as variáveis:

- `TELEGRAM_BOT_TOKEN`: token do bot
- `TELEGRAM_CHAT_IDS`: lista separada por vírgula (ex.: `123,456`)
  - Alternativamente, pode ser usado `TELEGRAM_CHAT_ID` único.

Sem essas variáveis, o envio retorna erro “Telegram não configurado”.

## Evitar duplicidade (slots) e reenvio forçado

O envio do digest registra log por **dia** + **slot** (ex.: `manual`, `morning`, `midday`, `evening`).

- Sem `force`, um envio já realizado com sucesso no mesmo dia/slot é “skipped”.
- Com `force=1`, o digest é reenviado mesmo que já exista log de sucesso.

Na UI de `/inbox/checklists/`, o botão de “Enviar aviso no Telegram” já envia com `force=1` após confirmação.

## Comando de gestão (CLI)

Existe um comando para envio via terminal:

- `python manage.py send_checklist_digest --slot manual --force`
- `python manage.py send_checklist_digest --date 2026-01-17 --slot morning`

Ele usa o mesmo código do backend e também registra em `ChecklistDigestLog`.
