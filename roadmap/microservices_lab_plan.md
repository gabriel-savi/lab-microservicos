# 🛒 Plano — Lab de Microsserviços (E-commerce)

> Transformar o monólito `python-api` em um laboratório de microsserviços com **8 serviços**, cobrindo comunicação síncrona (HTTP), assíncrona (eventos), API Gateway, Database-per-Service, resiliência e observabilidade de ponta a ponta.

## Visão Geral das Decisões

| Decisão | Escolha |
|---|---|
| Estrutura do repositório | Monorepo: `services/` + `shared/` (biblioteca comum) |
| Camada de entrada | Nginx como API Gateway (`:8080`) |
| Persistência | 1 container PostgreSQL → **1 database por serviço** |
| Entrega | Por fases: core síncrono → eventos assíncronos → gateway/polish |
| Código atual (`python-api`) | Vira o serviço de exemplo `services/messaging-demo` |

---

## 🎯 Arquitetura-Alvo

```mermaid
graph TB
    Client[Client / Postman] --> GW[Nginx API Gateway :8080]

    subgraph "Camada Síncrona (HTTP)"
        GW -->|/catalogo/*| CAT[catalog<br/>CRUD produtos + estoque]
        GW -->|/carrinho/*| CART[cart<br/>valida preço via HTTP]
        GW -->|/pedidos/*| ORD[order<br/>checkout + saga]
        GW -->|/pagamentos/*| PAY[payment<br/>simula falha/latência]
        CART -->|GET /products/:id| CAT
        ORD -->|GET /carts/:id| CART
        ORD -->|POST /payments<br/>CB + timeout| PAY
    end

    subgraph "Camada Assíncrona (RabbitMQ — topic orders.events)"
        ORD -->|publish order.paid| RMQ{RabbitMQ}
        RMQ --> INV[invoice-worker<br/>emite NF]
        RMQ --> LOG[logistics-worker<br/>agenda entrega]
        RMQ --> WAR[warranty-worker<br/>garantia estendida]
    end

    subgraph "Infraestrutura (existente)"
        PG[(PostgreSQL<br/>1 DB por serviço)]
        LOKI[Loki] --> GRAF[Grafana]
        PROM[Prometheus] --> GRAF
        TEMPO[Tempo] --> GRAF
        CAT --- PG
        CART --- PG
        ORD --- PG
        PAY --- PG
        INV --- PG
        LOG --- PG
        WAR --- PG
    end

    DEMO[messaging-demo<br/>Pub/Sub + Work Queue] -.-> RMQ
```

### Fluxo de negócio (happy path)

1. `POST /carrinho/:id/items` → cart valida produto/preço no catálogo (HTTP)
2. `POST /pedidos` → order busca carrinho → cria pedido `PENDING` → cobra pagamento (HTTP + Circuit Breaker)
3. Pagamento OK → pedido `PAID` → publica evento `order.paid` no topic exchange
4. invoice-worker emite NF e publica `invoice.issued`
5. logistics-worker agenda a entrega
6. warranty-worker registra garantia estendida (apenas produtos elegíveis)
7. Pagamento falhou → pedido `REJECTED` → publica `order.rejected` → workers ignoram (compensação)

---

## 📁 Estrutura de Pastas

```
logs-with-loki/
├── docker-compose.yml              # infra + todos os serviços
├── .env.example
├── config/
│   ├── nginx/nginx.conf            # [novo] API Gateway
│   ├── postgres/init.sql           # [novo] cria databases por serviço
│   ├── loki/  ├── grafana/  ├── prometheus/  ├── tempo/
├── shared/                         # [novo] biblioteca comum instalável
│   ├── pyproject.toml
│   └── lab_common/
│       ├── __init__.py
│       ├── logger.py               # JSON + contexto OTel (extraído do src atual)
│       ├── tracing.py              # init_tracing(service_name) + get_tracer()
│       ├── rabbitmq.py             # topologia declarativa + publish W3C
│       ├── worker.py               # [novo] retry/DLQ/idempotência/metrics server
│       ├── http_client.py          # [novo] requests + timeout + CB por downstream
│       ├── db.py                   # [novo] session factory por DATABASE_URL
│       └── health.py               # [novo] blueprint /health/live + /health/ready
├── services/
│   ├── messaging-demo/             # renomeado de python-api (refatorado p/ lab_common)
│   ├── catalog/                    # API Flask — produtos
│   ├── cart/                       # API Flask — carrinho
│   ├── order/                      # API Flask — pedidos + publicador de eventos
│   ├── payment/                    # API Flask — pagamentos simulados
│   ├── invoice/                    # worker assíncrono — emissão de NF
│   ├── logistics/                  # worker assíncrono — entrega
│   └── warranty/                   # worker assíncrono — garantia estendida
├── scripts/
│   ├── seed_catalog.sql            # produtos de exemplo
│   ├── smoke_test.sh               # fluxo end-to-end via gateway
│   └── demo_flow.sh                # cenário de aula
└── docs/                           # Postman + classroom guide atualizados
```

### Convenções de build (Docker)

- Build context **sempre na raiz** do repositório:

```yaml
catalog:
  build:
    context: .
    dockerfile: services/catalog/Dockerfile
```

- Cada Dockerfile copia `shared/` + seu serviço e roda `pip install ./shared -r service/requirements.txt`
- CMD alinhado para `python app.py` (elimina a ambiguidade do `flask run` + `FLASK_APP`)
- Base image e versões de dependências **mantidas** (Python 3.10, Flask, OTel 1.30) para não quebrar a instrumentação existente

---

## 📦 Topologia de Eventos (RabbitMQ)

| Elemento | Nome | Tipo | Observação |
|---|---|---|---|
| Exchange | `orders.events` | topic | Publicado pelo order-service |
| Routing keys | `order.paid`, `order.rejected`, `invoice.issued` | — | — |
| Queues | `invoice.order_paid`, `logistics.order_paid`, `warranty.order_paid` | durable | Cada worker tem a sua, bind por routing key |
| DLQ | `orders_dlq` | direct | nack sem requeue → DLQ (padrão já existente) |
| Headers | W3C Trace Context + `correlationId` | — | Propagação de ponta a ponta (já implementada) |

Os workers reutilizam o padrão do `consumer.py` atual: **retry com backoff exponencial** (3 tentativas), **idempotência** e **DLQ** — tudo embutido em `lab_common.worker.run_worker()`.

---

## 🗺️ Fases de Implementação

### Fase 0 — Fundação: `shared/` + reestruturação

> Sem mudança de comportamento: o lab atual deve continuar funcionando igual.

- [ ] Criar `shared/lab_common/` extraindo o `python-api/src/`:
  - [ ] `logger.py` — idêntico ao atual (JSON + `traceId`/`spanId`)
  - [ ] `tracing.py` — já parametrizado por `service_name`
  - [ ] `rabbitmq.py` — generalizar: `declare_topology()`, `publish(exchange, routing_key, msg, correlation_id)` com injeção W3C, `consume(queue, callback)`
  - [ ] `worker.py` — helper `run_worker(queue, handler, metrics_port)` com retry+backoff, DLQ, idempotência e `start_http_server`
  - [ ] `http_client.py` — `call(downstream, ...)` com `requests` + timeout + Circuit Breaker por serviço (pybreaker)
  - [ ] `db.py` — `create_session_factory()` lendo `DATABASE_URL` do env
  - [ ] `health.py` — blueprint com `/health/live` + `/health/ready` (postgres + rabbitmq opcional)
  - [ ] `pyproject.toml` para `pip install ./shared`
- [ ] Mover `python-api/` → `services/messaging-demo/` refatorando para importar de `lab_common`
- [ ] Dockerfiles com context na raiz (`context: .`)
- [ ] Atualizar `docker-compose.yml` (build contexts do messaging-demo)
- [ ] **Validação**: `docker compose up -d` → `POST /message` e `POST /task` funcionando, traces no Tempo e logs no Loki idênticos aos de hoje

### Fase 1 — Core síncrono: catálogo, carrinho, pedido, pagamento

- [ ] **catalog** (`catalog_db`):
  - [ ] CRUD `GET /products`, `GET /products/:id`, `POST /products`, `PUT /products/:id`
  - [ ] Campos: `name`, `price`, `stock`, `extended_warranty_eligible`
  - [ ] Seed em `scripts/seed_catalog.sql` (~5 produtos, 1 ou 2 elegíveis a garantia)
- [ ] **payment** (`payment_db`):
  - [ ] `POST /payments` → `PENDING → APPROVED/REJECTED`
  - [ ] `PAYMENT_FAILURE_RATE` (default ~0.2) e `PAYMENT_LATENCY_MS` via env — falha/latência didática p/ Circuit Breaker
- [ ] **cart** (`cart_db`):
  - [ ] `POST /carts/:id/items`, `GET /carts/:id`, `DELETE /carts/:id/items/:product_id`
  - [ ] Valida produto/preço no catálogo via `lab_common.http_client` (CB + timeout 2s)
- [ ] **order** (`order_db`):
  - [ ] `POST /orders` → `GET /carts/:id` → cria pedido `PENDING` → `POST /payments` (CB + timeout) → `PAID` ou `REJECTED`
  - [ ] `GET /orders/:id`; métrica `orders_created_total{status}`
- [ ] `config/postgres/init.sql` criando: `catalog_db`, `cart_db`, `order_db`, `payment_db`, `messages_db`
- [ ] Compose: +4 serviços com env vars (`DATABASE_NAME`, `POSTGRES_HOST`, `RABBITMQ_HOST`, `TEMPO_ENDPOINT`, etc.)
- [ ] Prometheus: 4 novos jobs (uma porta/serviço via `/metrics`)
- [ ] **Validação**: `scripts/smoke_test.sh` cobrindo catálogo → carrinho → pedido → pagamento; coleção Postman atualizada

### Fase 2 — Eventos assíncronos: NF, logística, garantia

- [ ] Topologia de eventos: exchange topic `orders.events` + queues + `orders_dlq` (em `lab_common`/compose)
- [ ] **order** publica `order.paid` (W3C headers + correlationId) após pagamento OK e `order.rejected` na falha
- [ ] **invoice-worker** (`invoice_db`):
  - [ ] Consome `order.paid` → simula emissão (latência 2–3s) → persiste número de NF sequencial
  - [ ] Publica `invoice.issued`
  - [ ] Falha simulada ocasional (~20%) → demonstra retry + DLQ
- [ ] **logistics-worker** (`logistics_db`): consome `order.paid` → cria entrega `SCHEDULED`
- [ ] **warranty-worker** (`warranty_db`):
  - [ ] Consome `order.paid` → enriquece com dados do catálogo (HTTP)
  - [ ] Registra garantia estendida **apenas** se item tiver `extended_warranty_eligible=true`
- [ ] Os 3 workers usam `lab_common.worker.run_worker()` (retry/DLQ/idempotência grátis)
- [ ] Prometheus: jobs `dns_sd` por worker; dashboard com painéis de eventos e DLQ
- [ ] **Validação**: um `POST /pedidos` gera um trace único no Tempo (HTTP → evento → 3 workers); mesma `correlationId` consultável no Loki

### Fase 3 — Gateway, resiliência e polish

- [ ] **Nginx API Gateway** (`:8080`):
  - [ ] Roteia `/catalogo/*` → catalog, `/carrinho/*` → cart, `/pedidos/*` → order, `/pagamentos/*` → payment
  - [ ] `/docs` de cada serviço acessível via path (Swagger)
  - [ ] Gera/propaga `X-Correlation-ID`
  - [ ] Rate limit simples (didático)
- [ ] **Resiliência reforçada**:
  - [ ] Timeouts explícitos em todas as chamadas inter-serviço
  - [ ] Demo em aula: `PAYMENT_FAILURE_RATE=1.0` + derrubar payment → pedido rejeita rápido com 503 (CB aberto)
- [ ] **Compensação didática**: `order.rejected` → logistics/warranty registram `IGNORED` (saga simplificada)
- [ ] Dashboard Grafana reorganizado por serviço (RED + containers + filas + eventos)
- [ ] `scripts/demo_flow.sh` (cenário de aula) e `test_load.py` adaptado para o fluxo de pedidos
- [ ] Atualizar `README.md`, `docs/classroom_guide.md` e coleção do Postman; diagrama mermaid final

---

## 🧠 Conceitos Cobertos pelo Lab Final

| Conceito | Onde ver na prática |
|---|---|
| API Gateway | Nginx roteando por path + rate limit |
| Database-per-Service | 7 databases no PostgreSQL, cada serviço só acessa o seu |
| Comunicação síncrona (HTTP) | cart→catalog, order→cart, order→payment |
| Comunicação assíncrona (eventos) | order→(invoice, logistics, warranty) via topic exchange |
| Pub/Sub vs Work Queue | messaging-demo (fanout vs direct) — referência didática |
| Circuit Breaker entre serviços | order→payment e cart→catalog via `lab_common.http_client` |
| Saga / compensação | `order.rejected` → workers ignoram/registram IGNORED |
| DLQ + Retry c/ Backoff | workers da Fase 2 + messaging-demo |
| Idempotência | `lab_common.worker` (cache por correlationId) |
| Correlation ID + W3C Trace Context | gateway → HTTP → evento → worker → banco |
| Health Checks | blueprint compartilhado `/health/live` + `/health/ready` |
| Observabilidade (3 pilares) | Loki + Prometheus + Tempo com 12+ processos |
| Escalabilidade horizontal | workers replicáveis + `dns_sd` no Prometheus |

---

## ⚠️ Riscos e Mitigações

| Risco | Mitigação |
|---|---|
| `docker-compose.yml` crescer muito (~400+ linhas) | Âncoras YAML (`x-app-defaults`) para env/logging/restart comuns |
| Build context raiz copiando tudo | `.dockerignore` na raiz excluindo `.git`, `docs`, `config` |
| Conflito de porta dos workers (metrics) | Cada worker no seu container: todos usam `8000` internamente, `dns_sd` por nome |
| Duplicação entre serviços (copiar/colar) | `lab_common` cobre logger/tracing/rabbitmq/worker/http/db/health — serviço só tem regra de negócio |
| Quebra do lab atual na Fase 0 | Critério de validação explícito: `/message` e `/task` devem continuar iguais antes de avançar |
| Portas dos serviços no host | Serviços **não** expõem porta no host; só o gateway (`8080`) — debug via `docker compose exec` ou Swagger pelo gateway |

---

## ✅ Ordem de Execução Recomendada

1. **Fase 0** primeiro — destrava tudo o resto e garante reutilização
2. **Fase 1** — 4 serviços síncronos validados juntos com `smoke_test.sh`
3. **Fase 2** — 3 workers assíncronos + topologia de eventos
4. **Fase 3** — gateway + resiliência + dashboards + docs

> Cada fase termina com o lab **100% funcional** (`docker compose up -d` + critérios de validação), permitindo pausar e retomar a qualquer momento.
