# SAMU Normas: Manual Digital Interativo

> *De um arquivo PDF estático para uma aplicação Full Stack de alta performance.*

Este projeto nasceu da necessidade de transformar o **Manual de Normas e Rotinas do SAMU 192** — originalmente um documento PDF extenso e de difícil navegação via mobile — em uma **ferramenta digital interativa, buscável e responsiva**.

O objetivo não é apenas "digitalizar texto", mas oferecer uma **Experiência de Usuário (UX)** que respeite o cenário crítico de quem usa: profissionais de socorro que precisam de informação exata em segundos, muitas vezes em situações de estresse.

## ⚡ A Solução Técnica & UX

Para atingir a fluidez necessária, o projeto adota uma arquitetura moderna, desacoplando a inteligência das regras (Backend) da experiência de consumo (Frontend).

### Frontend: React + Vite
A interface foi construída como uma SPA (Single Page Application) utilizando **React**, garantindo que a navegação entre normas seja instantânea, sem recarregamentos de página.

*   **Performance:** Uso do **Vite** para um bundle otimizado e carregamento ultrarrápido.
*   **Interatividade:** Filtros em tempo real por categoria (Operacional, RH, Logística) e perfil Profissional (Médico, Condutor, Rádio).
*   **Animações & Micro-interações:** A aplicação utiliza transições suaves para filtrar e exibir cards. Isso não é apenas estético; reduz a carga cognitiva do usuário, guiando o olhar para a informação relevante de forma orgânica.
*   **Mobile-First:** Layout pensado primordialmente para telas de smartphones, onde o manual é mais consultado.

### Backend: Python & Django
O "cérebro" da aplicação. O Django não serve apenas JSON; ele gerencia a complexidade das normas.

*   **Admin Customizado:** Uma interface administrativa robusta para que a coordenação possa atualizar regras sem tocar em código.
*   **API REST Agnostic:** Serve os dados para o React, mas está pronta para alimentar apps nativos (iOS/Android) futuramente.

## 🛠️ Stack Tecnológico

*   **Frontend:** React 18, Vite, CSS Modules / Tailwind (para estilização utilitária).
*   **Backend:** Python 3.12, Django 5, Django REST Framework.
*   **Infraestrutura:** Docker, Docker Compose, Nginx (Proxy Reverso), MariaDB (Produção).
*   **Qualidade:** Testes automatizados (Pytest), CI/CD (GitHub Actions).

## 📁 Organização do Código

O repositório segue uma estrutura limpa e direta na raiz, facilitando o onboarding de novos desenvolvedores:

*   `/frontend`: Código fonte da aplicação React.
*   `/backend` (e pastas Django): Lógica de negócios e API.
*   `/nginx` & `/infra`: Configurações de container e deploy.
*   `/scripts`: Automações de deploy e seed de banco de dados.

## 🚀 Como Executar

A documentação técnica detalhada para setup e deploy encontra-se nos arquivos dedicados:

*   **Desenvolvimento:** [README_DEV.md](README_DEV.md) (Docker, variáveis de ambiente, hot-reload).
*   **Produção:** [README_DEPLOY.md](README_DEPLOY.md) (Build de imagens, SSL, Gunicorn).

## 🎯 Por que este projeto importa?

Transformar burocracia em usabilidade. Ao converter documentos governamentais estáticos em software vivo, impactamos diretamente a eficiência do serviço público e a segurança dos procedimentos de saúde.

---
*Desenvolvido com foco em Código Limpo, Arquitetura Escalável e UX.*
