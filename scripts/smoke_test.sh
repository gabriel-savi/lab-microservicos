#!/bin/bash
echo "==> Catalogo"
curl -s http://localhost:8080/catalogo/products | head -c 80
echo -e "\n==> Carrinho"
curl -s -X POST http://localhost:8080/carrinho/carts/smoke/items -H "Content-Type: application/json" -d '{"productId":2,"quantity":1}' 
echo -e "\n==> Pedido"
curl -s -X POST http://localhost:8080/pedidos/orders -H "Content-Type: application/json" -d '{"cartId":"smoke"}'
echo -e "\n==> OK"
