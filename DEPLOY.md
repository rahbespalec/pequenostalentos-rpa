# Publicação na internet

## Opção simples

Use uma VPS Linux com Docker instalado. Suba os arquivos e execute:

```bash
cp .env.example .env
# edite .env e troque SECRET_KEY e RUNNER_TOKEN

docker compose up -d --build
```

A porta 8080 expõe o laboratório.

## HTTPS / domínio

Coloque Caddy, Nginx ou Traefik na frente do serviço `web` e use HTTPS. O arquivo `Caddyfile` contém uma configuração inicial.

## Capacidade para ~30 simultâneos

Cada sessão cria um Chromium isolado. O consumo depende da página automatizada e do tamanho das janelas, mas 30 Chromes podem consumir vários GB de RAM. Para começar, use uma VPS de pelo menos 8 vCPU / 16 GB RAM e monitore. Se necessário, aumente para 32 GB e/ou distribua os runners em mais de um servidor.

Antes de anunciar para o público, configure:

- HTTPS obrigatório;
- rate limiting por IP/sessão;
- limite de sessões por IP;
- logs e métricas;
- limpeza de containers órfãos;
- rede de saída do sandbox com allowlist;
- autenticação entre web e runner;
- backups somente dos dados necessários;
- política de privacidade se forem coletados nomes ou outros dados.
