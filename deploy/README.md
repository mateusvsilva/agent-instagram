# Implantação — artefatos da Seção 5 do PLANO

Este diretório e os arquivos Docker na raiz cobrem as três lacunas de produção:
empacotamento (Docker/systemd), serviço com auto-restart e backup automatizado do SQLite.

Escolha **um** caminho de execução: **Docker** (recomendado) ou **bare-metal (systemd)**.
O **backup** funciona igual nos dois.

---

## Caminho A — Docker (recomendado)

Arquivos: [`Dockerfile`](../Dockerfile), [`docker-compose.yml`](../docker-compose.yml), [`.dockerignore`](../.dockerignore).

```bash
# na VPS, dentro do repositório
cp .env.example .env          # preencher TODAS as credenciais (ver PLANO seção 4)
# colocar o logo em assets/brand/logo.png se LOGO_ENABLED=true

docker compose up -d --build  # sobe em background e reinicia sozinho (restart: unless-stopped)
docker compose logs -f        # acompanhar
```

- **Sem portas publicadas** — o Telegram é por polling, então nada é exposto na rede.
- **Estado persistente** fica no host em `./data` (bind mount): banco, imagens e logs sobrevivem a `up`/`down`/rebuild.
- **Auto-restart e boot:** `restart: unless-stopped` reinicia em falha e quando a VPS liga (com o serviço Docker habilitado no boot).

Atualizar versão:
```bash
git pull && docker compose up -d --build
```

---

## Caminho B — Bare-metal (systemd + venv)

Arquivo: [`instagram-agent.service`](instagram-agent.service). Use se **não** quiser Docker.

```bash
# pré-requisitos: python3.11-venv, dependências instaladas no .venv (ver PLANO seção 5.2)
sudo cp deploy/instagram-agent.service /etc/systemd/system/
# ajuste User= e os caminhos dentro do arquivo se seu usuário/pasta forem diferentes de deploy / /home/deploy/instagram_agents
sudo systemctl daemon-reload
sudo systemctl enable --now instagram-agent
sudo systemctl status instagram-agent
journalctl -u instagram-agent -f
```

Auto-restart (`Restart=on-failure`) e boot (`enable`) ficam a cargo do systemd.

---

## Backup automatizado do SQLite (para os dois caminhos)

Arquivos: [`backup-db.sh`](backup-db.sh) + timer systemd
([`.service`](instagram-agent-backup.service) / [`.timer`](instagram-agent-backup.timer)).

O script usa `sqlite3 .backup` (consistente com o app rodando), comprime, aplica
retenção e opcionalmente envia off-site. Como o banco fica em `./data/db` no host
nos dois caminhos, o mesmo script serve para Docker e bare-metal.

### Opção 1 — timer systemd (recomendado)
```bash
sudo cp deploy/instagram-agent-backup.service /etc/systemd/system/
sudo cp deploy/instagram-agent-backup.timer   /etc/systemd/system/
# ajuste os caminhos/Environment dentro do .service
sudo systemctl daemon-reload
sudo systemctl enable --now instagram-agent-backup.timer
systemctl list-timers instagram-agent-backup   # confere o próximo disparo (03:00)
```

### Opção 2 — cron
```bash
# crontab -e (usuário deploy)
0 3 * * * /home/deploy/instagram_agents/deploy/backup-db.sh >> /home/deploy/instagram_agents/data/backup.log 2>&1
```

### Testar agora e restaurar
```bash
# testar (gera um .db.gz em ./backups)
DB_PATH=./data/db/agent.db BACKUP_DIR=./backups ./deploy/backup-db.sh

# restaurar: parar o serviço, descomprimir por cima do banco, subir de novo
docker compose down            # ou: sudo systemctl stop instagram-agent
gunzip -c backups/agent-AAAA-MM-DD_HHMM.db.gz > data/db/agent.db
docker compose up -d           # ou: sudo systemctl start instagram-agent
```

> **Off-site:** backup na mesma VPS não protege contra perda do servidor.
> Defina `OFFSITE_CMD` (ex.: `rclone copy "$1" b2:bucket/impressam-backups`)
> no `.service` ou no ambiente do cron para copiar para fora.

---

## Notas importantes

- **Nunca** suba o `.env` para a imagem/repositório — o `.dockerignore` e o `.gitignore` já o excluem.
- **Budget em memória:** reiniciar o processo zera o contador de gasto do período. Evite `restart`/`up --build` repetidos no mesmo dia (ver PLANO seção 8).
- **tzdata** já vai na imagem Docker (necessário para `America/Sao_Paulo`); no bare-metal o SO já tem.
