# SAMU Normas

Este repositório contém o código fonte da plataforma de consulta e gerenciamento de normas e protocolos internos do SAMU 192. A aplicação visa facilitar o acesso a regras operacionais, protocolos de atendimento e diretrizes administrativas para as equipes de socorro.

## 📁 Estrutura do Projeto

A organização do repositório é dividida em duas grandes áreas:

*   **`Perguntas/`**: Contém a aplicação principal (Full Stack).
    *   **Backend:** Desenvolvido em **Django** (Python). Responsável pela lógica de negócios, gestão de usuários, administração das normas via Django Admin e API.
    *   **Frontend:** SPA desenvolvida em **React** (Vite). Responsável pela interface moderna e reativa para consulta rápida das normas.
    *   **Infraestrutura:** Arquivos de configuração Docker (`Dockerfile`, `docker-compose*.yml`) para orquestração dos serviços (App Web, Banco de Dados, Nginx).
*   **`site/`**: Uma versão _standalone_ (estática) simplificada da consulta de normas, útil para situações de contingência ou acesso offline/leve.

## 🚀 Tecnologias

*   **Linguagens:** Python 3.12+, JavaScript/TypeScript.
*   **Frameworks:** Django 5.x, React 18+.
*   **Banco de Dados:** MariaDB 11.4 (Produção), SQLite (Desenvolvimento/CI).
*   **Servidor Web/Proxy:** Nginx 1.27.
*   **Containerização:** Docker & Docker Compose.

## 🛠️ Como Executar

A documentação detalhada para desenvolvimento e deploy está localizada dentro da pasta `Perguntas/`.

*   **Para Desenvolvedores:** Consulte [Perguntas/README_DEV.md](Perguntas/README_DEV.md) ou a documentação completa em [Perguntas/docs/DEV_GUIDE.md](Perguntas/docs/DEV_GUIDE.md). Lá você encontrará instruções para rodar o ambiente com Docker, configurar variáveis de ambiente e executar testes.
*   **Para Deploy (Produção):** Consulte [Perguntas/README_DEPLOY.md](Perguntas/README_DEPLOY.md) para instruções sobre build de imagens, configuração de servidor e uso de certificados SSL.

## 📚 Funcionalidades Principais

*   **Busca Semântica/Texto:** Localização rápida de normas por palavras-chave.
*   **Categorização:** Filtros por setor (Operacional, RH, Logística) e perfil de acesso (Médico, Condutor, Rádio).
*   **Painel Administrativo:** Interface do Django Admin para criação e edição fácil das regras.
*   **Autenticação:** Sistema de login para acesso a áreas restritas e auditoria.

## 🤝 Contribuição

1.  Faça um Fork do projeto.
2.  Crie uma Branch para sua Feature (`git checkout -b feature/NovaFeature`).
3.  Faça o Commit (`git commit -m 'Add some NovaFeature'`).
4.  Push para a Branch (`git push origin feature/NovaFeature`).
5.  Abra um Pull Request.

---
*© SAMU 192 - Serviço de Atendimento Móvel de Urgência*
