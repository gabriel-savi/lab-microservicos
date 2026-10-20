#!/usr/bin/env bash
# Demonstra resiliência: derruba o payment, observa o Circuit Breaker abrir e o pedido rejeitar rápido.
set -euo pipefail

GW="http://localhost:8080"
CART_ID="chaos-$(date +%s)"

echo "==> 1. Prepara carrinho"
curl -s -X POST "$GW/api/v1/carrinho/carts/$CART_ID/items" -H "Content-Type: application/json" -d '{"productId":2,"quantity":1}' >/dev/null

echo "==> 2. Derruba o serviço de pagamento"
docker compose stop payment

echo "==> 3. Dispara pedidos e observa a rejeição rápida (Circuit Breaker)"
for i in 1 2 3 4 5; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$GW/api/v1/pedidos/orders" -H "Content-Type: application/json" -d "{\"cartId\":\"$CART_ID\"}")
  echo "  tentativa $i → HTTP $CODE"
done

echo "==> 4. Estado do Circuit Breaker no log do order"
docker compose logs order 2>/dev/null | grep -iE 'rejected|circuit|breaker' | tail -5 || true

echo "==> 5. Restaura o payment"
docker compose start payment
sleep 3

echo "==> 6. Após restaurar, um novo pedido deve funcionar"
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$GW/api/v1/pedidos/orders" -H "Content-Type: application/json" -d "{\"cartId\":\"$CART_ID\"}")
echo "  HTTP $CODE"