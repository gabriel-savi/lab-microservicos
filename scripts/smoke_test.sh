#!/usr/bin/env bash
# Smoke test: valida os endpoints públicos em poucos segundos.
set -euo pipefail

GW="http://localhost:8080"

echo "==> health"
curl -fsS "$GW/health" >/dev/null && echo "  ok"

echo "==> catálogo"
curl -fsS "$GW/api/v1/catalogo/products" >/dev/null && echo "  ok"

echo "==> carrinho"
curl -fsS -X POST "$GW/api/v1/carrinho/carts/smoke/items" -H "Content-Type: application/json" \
  -d '{"productId":2,"quantity":1}' >/dev/null && echo "  ok"

echo "==> pedido"
curl -s -X POST "$GW/api/v1/pedidos/orders" -H "Content-Type: application/json" \
  -d '{"cartId":"smoke"}'; echo

echo "==> smoke test concluído"