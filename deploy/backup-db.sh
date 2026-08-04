#!/usr/bin/env bash
#
# Backup do banco SQLite do Instagram Agent (impressam).
#
# Usa `sqlite3 .backup`, que é seguro com o app rodando (backup a quente,
# consistente, sem travar o processo). Funciona tanto no deploy Docker
# (o banco fica no bind mount ./data/db) quanto no deploy bare-metal.
#
# Configurável por variáveis de ambiente (com defaults):
#   DB_PATH        caminho do banco            (default: ./data/db/agent.db)
#   BACKUP_DIR     pasta de destino            (default: ./backups)
#   RETENTION_DAYS dias a manter               (default: 14)
#   OFFSITE_CMD    comando opcional de cópia off-site (ver exemplo abaixo)
#
# Uso manual:   ./deploy/backup-db.sh
# Via cron:     0 3 * * * /home/deploy/instagram_agents/deploy/backup-db.sh >> /home/deploy/instagram_agents/data/backup.log 2>&1
# Via systemd:  ver deploy/instagram-agent-backup.{service,timer}

set -euo pipefail

DB_PATH="${DB_PATH:-./data/db/agent.db}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

timestamp="$(date +%F_%H%M)"
dest="${BACKUP_DIR}/agent-${timestamp}.db"

if [[ ! -f "$DB_PATH" ]]; then
  echo "[backup] ERRO: banco não encontrado em '$DB_PATH'" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

# Backup consistente mesmo com o app escrevendo.
sqlite3 "$DB_PATH" ".backup '${dest}'"
gzip -f "$dest"
echo "[backup] ok: ${dest}.gz"

# Retenção: remove backups mais antigos que RETENTION_DAYS.
find "$BACKUP_DIR" -name 'agent-*.db.gz' -mtime "+${RETENTION_DAYS}" -delete
echo "[backup] retenção aplicada (> ${RETENTION_DAYS} dias removidos)"

# Cópia off-site opcional. Recebe o arquivo gerado como $1.
# Ex.: export OFFSITE_CMD='rclone copy "$1" b2:meu-bucket/impressam-backups'
if [[ -n "${OFFSITE_CMD:-}" ]]; then
  # shellcheck disable=SC2016
  bash -c "$OFFSITE_CMD" _ "${dest}.gz"
  echo "[backup] off-site enviado"
fi
