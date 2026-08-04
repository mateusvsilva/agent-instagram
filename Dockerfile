# Instagram Agent (impressam) — imagem de produção
# Processo único e sempre-ligado. Telegram por polling: NÃO expõe portas.
FROM python:3.11-slim

# tzdata: o scheduler usa America/Sao_Paulo (zoneinfo) e o slim não traz o
#   banco de timezones do sistema.
# sqlite3: usado pelo script de backup.
# gosu: derruba privilégio de root -> appuser no entrypoint (ver docker-entrypoint.sh).
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata sqlite3 gosu \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=America/Sao_Paulo

WORKDIR /app

# Instala dependências primeiro para aproveitar o cache de camadas.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código.
COPY . .

# Usuário sem privilégios que rodará o app.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data/db /app/data/images /app/data/templates \
    && chown -R appuser:appuser /app \
    && chmod +x /app/docker-entrypoint.sh

# data/ é persistido via volume no docker-compose (banco, imagens, logs).
VOLUME ["/app/data"]

# O entrypoint inicia como root só para ajustar o dono do bind mount e então
# derruba para appuser (ver docker-entrypoint.sh). NÃO usamos "USER appuser"
# de propósito: o container precisa começar como root para corrigir o mount.
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "-m", "src.main"]
