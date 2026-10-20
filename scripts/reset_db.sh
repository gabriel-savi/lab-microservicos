#!/usr/bin/env bash
# Cria (idempotente) todos os databases por serviço sem apagar o volume existente.
# Usado quando o postgres já foi inicializado (init.sql só roda em volume vazio).
set -euo pipefail

USER="${POSTGRES_USER:-admin}"
CONTAINER="${POSTGRES_CONTAINER:-postgres}"
DB_NAMES=(
  catalog_db
  cart_db
  order_db
  payment_db
  invoice_db
  logistics_db
  warranty_db
)

for db in "${DB_NAMES[@]}"; do
  if docker compose exec -T "$CONTAINER" psql -U "$USER" -d postgres -tAc \
      "SELECT 1 FROM pg_database WHERE datname = '$db'" | grep -q 1; then
    echo "✔ $db já existe"
  else
    docker compose exec -T "$CONTAINER" psql -U "$USER" -d postgres -c "CREATE DATABASE $db;"
    echo "✔ $db criado"
  fi
done