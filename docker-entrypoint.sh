#!/bin/sh
# Entrypoint de produção.
#
# O volume ./data é um bind mount vindo do host, então costuma chegar com o
# dono do host (ex.: root), "cobrindo" o chown feito na imagem. Aqui, ainda
# como root, garantimos as subpastas e o dono correto e então DERRUBAMOS o
# privilégio para rodar o app como usuário sem privilégios (appuser).
set -e

if [ "$(id -u)" = "0" ]; then
  mkdir -p /app/data/db /app/data/images /app/data/templates
  chown -R appuser:appuser /app/data
  exec gosu appuser "$@"
fi

# Se já não for root (ex.: container rodado com --user), apenas executa.
exec "$@"
