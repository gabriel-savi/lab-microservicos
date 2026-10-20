#!/usr/bin/env bash
# Gera carga no fluxo de pedidos (default 50 pedidos, configurável).
set -euo pipefail

GW="http://localhost:8080"
N="${1:-50}"

echo "==> Enviando $N pedidos..."
ok=0; rej=0
for i in $(seq 1 "$N"); do
  CART_ID="load-$$-$i"
  curl -s -o /dev/null -X POST "$GW/api/v1/carrinho/carts/$CART_ID/items" \
    -H "Content-Type: application/json" -d '{"productId":3,"quantity":1}'
  STATUS=$(curl -s -X POST "$GW/api/v1/pedidos/orders" -H "Content-Type: application/json" -d "{\"cartId\":\"$CART_ID\"}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','ERR'))")
  if [ "$STATUS" = "PAID" ]; then ok=$((ok+1)); else rej=$((rej+1)); fi
  printf "\r  ok=%d rejeitados=%d" "$ok" "$rej"
done
echo
echo "==> Concluído. Acompanhe métricas no Prometheus (orders_created_total) e filas no RabbitMQ."