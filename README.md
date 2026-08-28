# Laboratório de RPA - Pequenos Talentos

Plataforma web educacional para ensinar automação com Python + Selenium sem instalar nada no computador do aluno.

## Arquitetura

- **Frontend:** HTML/CSS/JavaScript + Monaco Editor via CDN.
- **API:** Flask.
- **Runner manager:** serviço separado que cria um container isolado por execução.
- **Browser:** Chromium + ChromeDriver + Selenium + Xvfb dentro do container do aluno.
- **Tela virtual:** screenshots JPEG atualizados no navegador durante a execução.
- **Concorrência:** configurada para até 30 sessões simultâneas (`MAX_SESSIONS=30`).
- **Limites:** CPU, RAM, tempo de execução e tamanho do código são configuráveis.

## Rodar localmente

Requisitos: Docker Desktop/Engine e Docker Compose.

```bash
docker compose up --build
```

Abra `http://localhost:8080`.

## Publicar

1. Coloque a aplicação em uma VPS/servidor com Docker.
2. Aponte um domínio para o servidor.
3. Coloque HTTPS na frente (Caddy, Traefik ou Nginx + Let's Encrypt).
4. Altere `SECRET_KEY` e `RUNNER_TOKEN` no `.env`.
5. Para 30 acessos simultâneos, recomendo uma máquina com pelo menos 8 vCPU e 16 GB RAM, começando com 20 sessões e aumentando conforme o uso real. Chrome consome bastante memória.

## Segurança

O código do aluno é executado em containers descartáveis e com limites de CPU/memória. O editor não expõe o shell do host.

**Importante:** este projeto é um MVP educacional. Para abrir a execução de Python arbitrário para a internet pública, faça hardening adicional antes de produção: rede de saída restrita/allowlist, autenticação do runner, observabilidade, rate limiting, limpeza de containers órfãos, HTTPS, logs e revisão de segurança da sandbox. Não considere uma simples lista AST como uma sandbox de segurança por si só.

## Desafios

O desafio inicial é servido pelo próprio Flask em `/desafio`. O código inicial do editor já aponta para esse endereço.
