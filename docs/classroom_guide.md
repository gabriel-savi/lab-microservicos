# 🎓 Roteiro de Aula Prática — Lab de Microsserviços (E-commerce)

Runbook do instrutor para conduzir a aula de **Arquitetura de Microsserviços** com o e-commerce de exemplo: catálogo, carrinho, pedido, pagamento (síncrono) e NF, logística e garantia (assíncrono).

## 📋 Preparação (antes da aula)

```bash
cd ~/Developer/logs-with-loki
cp .env.example .env                      # senhas padrão
docker compose down -v                    # garante estado limpo
docker compose up -d --build              # sobe tudo (1–2 min)
curl http://localhost:8080/health         # deve retornar {"status":"UP"}
```

Verificar manualmente:
- **Grafana** http://localhost:3000 (admin / `testloki`) → dashboards provisionados
- **RabbitMQ** http://localhost:15672 (admin / `passw123`) → exchange `orders.events`
- **Prometheus** http://localhost:9090 → 10 targets `up` (só `cadvisor` down no macOS)

## 🚀 Demo 1 — Fluxo feliz (síncrono + assíncrono)

```bash
./scripts/demo_flow.sh
```

Roteiro de explicação:
1. `GET /api/v1/catalogo/products` → catálogo (CRUD + estoque + elegibilidade de garantia)
2. `POST /api/v1/carrinho/carts/:id/items` → carrinho **valida o produto no catálogo via HTTP**
3. `POST /api/v1/pedidos/orders` → order **reserva estoque**, chama o **pagamento** (HTTP + circuit breaker) e, se aprovado, grava pedido `PAID` + **evento no Outbox** (mesma transação)
4. `outbox_relay` publica `order.paid` no RabbitMQ (at-least-once)
5. `invoice-worker`, `logistics-worker` e `warranty-worker` consomem e persistem

**Perguntas para a turma:**
- Por que o carrinho não guarda o preço "confiável" e valida no catálogo? (fonte de verdade única)
- Por que a NF/logística/garantia são assíncronas e não no mesmo request? (desacoplamento, resiliência)

## 💥 Demo 2 — Resiliência (Circuit Breaker)

```bash
./scripts/demo_chaos.sh
```

Roteiro:
1. `payment` é derrubado
2. Os pedidos começam a **falhar rápido** (503) depois que o Circuit Breaker abre — sem esperar timeout
3. `payment` é restaurado; o CB volta a `closed` depois do `reset_timeout`

**Perguntas:**
- O que aconteceria sem circuit breaker? (cascata de falhas, threads presas em timeout)
- Onde mais caberia um CB? (cart→catalog)

## 🔄 Demo 3 — Saga e compensação

Configure falha total: pare o `payment` OU `PAYMENT_FAILURE_RATE=1.0` no `.env` + `docker compose up -d payment`.

Fluxo:
1. `order` **reserva estoque** (decrementa no catálogo)
2. Pagamento falha → `order` **libera o estoque** (compensação) e grava `order.rejected` no Outbox
3. `logistics-worker` marca `CANCELLED`; `warranty-worker` ignora (`SKIPPED`)

**Perguntas:**
- Por que a compensação é "best-effort" e o que fazer se ela falhar? (retry, DLQ, operação manual)
- Diferença entre **saga orquestrada** e **coreografada** (aqui o `order` orquestra).

## 🧾 Demo 4 — Idempotência e Outbox

- Re-publicar uma mensagem duplicada (`order.paid`) e mostrar que **não duplica** NF/entrega (constraint UNIQUE).
- Matar o RabbitMQ antes do publish e religar → o `outbox_relay` entrega o evento pendente.

**Perguntas:**
- Por que mensagens podem chegar duplicadas? (at-least-once, retries)
- Outbox vs publicar direto após o commit: qual o risco do segundo?

## 📊 Demo 5 — Observabilidade de ponta a ponta

1. Rode `./scripts/load_orders.sh 50`
2. **Grafana → E-commerce Microservices**: pedidos por status, pagamentos, eventos processados, erros/DLQ
3. **Tempo**: escolha um trace e mostre o caminho completo `gateway → order → cart/payment → rabbitmq → invoice/logistics/warranty`
4. **Loki**: filtre por `correlationId` e pule do log para o trace (e vice-versa)

**Perguntas:**
- Qual o papel do `correlationId` vs `traceId`? (negócio vs técnico)
- Métricas **RED** (Rate, Errors, Duration) — quais painéis faltam para fechar o método?

## 🧠 Discussão final (trade-offs)

| Tema | Discussão |
|---|---|
| Síncrono vs assíncrono | quando usar HTTP e quando usar eventos (consistência vs acoplamento) |
| Database-per-service | por que não compartilhar o banco? (falha isolada, autonomia) |
| API Gateway | centralização de cross-cutting (rate limit, correlation id, futura auth) |
| Versionamento | por que `/api/v1`? breaking changes |
| CI | o pipeline (`.github/workflows/ci.yml`) valida lint + build + smoke |

## ⏱️ Cronograma sugerido (1h30)

1. (10 min) Arquitetura no quadro + subir a stack
2. (15 min) Demo 1 — fluxo feliz + tracing no Tempo
3. (15 min) Demo 2 — circuit breaker
4. (15 min) Demo 3 — saga/compensação
5. (15 min) Demo 4 — idempotência + outbox
6. (15 min) Demo 5 — observabilidade + carga
7. (5 min) Discussão final