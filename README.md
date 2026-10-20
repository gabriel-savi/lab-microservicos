# Observability Lab: Loki, Grafana, Prometheus, Tempo & RabbitMQ

Laboratório de observabilidade e mensageria para uso em aulas de **Arquitetura de Microsserviços**. Este projeto demonstra na prática conceitos como logs centralizados, métricas, distributed tracing, comunicação assíncrona, resiliência e persistência.

## Stack

| Serviço | Função |
|---|---|
| **Loki** | Agregação e armazenamento de logs |
| **Grafana** | Visualização de logs, métricas e traces |
| **Prometheus** | Coleta e armazenamento de métricas |
| **Tempo** | Armazenamento de traces distribuídos (OTLP) |
| **PostgreSQL** | Persistência de dados das mensagens processadas |
| **cAdvisor** | Exporta métricas de hardware/CPU/RAM dos containers |
| **RabbitMQ** | Message broker (comunicação assíncrona) |
| **Python API** | API REST Flask — produz mensagens e expõe métricas/traces |
| **Python Consumer** | Worker assíncrono — consome mensagens da fila Pub/Sub, persiste e gera traces |
| **Python Task Consumer** | Worker assíncrono — consome tarefas da fila Work Queue, processa e gera traces |

## Pré-requisitos

- [Docker](https://www.docker.com/)
- [Docker Compose](https://docs.docker.com/compose/)

## Como executar

```sh
git clone https://github.com/josemanzoli/logs-with-loki
cd logs-with-loki

# Copie e configure as variáveis de ambiente
cp .env.example .env   # ajuste as senhas se necessário

docker compose up -d
```

## Acessos

| Interface | URL | Credenciais |
|---|---|---|
| **Grafana** | http://localhost:3000 | admin / `GRAFANA_PASSWORD` do `.env` |
| **Prometheus** | http://localhost:9090 | — |
| **Tempo (API)** | http://localhost:3200 | — |
| **RabbitMQ Management** | http://localhost:15672 | admin / `RABBITMQ_PASSWORD` do `.env` |
| **cAdvisor** | http://localhost:8080 | — |
| **API Endpoints** | http://localhost:5000/messages | — |
| **API Swagger (OpenAPI)** | http://localhost:5000/docs | — |

## Tópicos cobertos na aula

- **Logs centralizados** com Loki + Promtail + Grafana
- **Distributed Tracing** com **Grafana Tempo** — rastreie o fluxo completo (API → RabbitMQ → Consumers de mensagens e tarefas)
- **Trace-to-Logs** — Pule de um trace no Tempo diretamente para os logs no Loki usando o `correlationId`
- **Métricas de aplicação** com `prometheus_client` (Flask)
- **Métricas de infraestrutura** com cAdvisor (CPU/RAM por container)
- **Persistência SQL** — Mensagens salvas em **PostgreSQL** via worker assíncrono
- **Comunicação assíncrona** via RabbitMQ (DLQ, Retry com Backoff, Idempotência)
- **Resiliência (Circuit Breaker)** — Proteção de falhas em cascata com `pybreaker`
- **Health Checks Profundos** — Liveness e Readiness probes integradas ao estado do circuito
- **Painel de DLQ e Erros** — visualiza taxas de erro dos consumers e dead letter queue no Grafana
- **Métricas de Filas RabbitMQ** — visualiza o tamanho das filas (logs, tasks e DLQ) em tempo real no Grafana

## Estrutura do projeto

```
logs-with-loki/
├── config/
│   ├── grafana/provisioning/  # Datasources automáticos (Loki, Prometheus, Tempo)
│   ├── loki/                  # Configuração do Loki
│   ├── promtail/              # Configuração do Promtail
│   ├── prometheus/            # Scrape config p/ API e cAdvisor
│   └── tempo/                 # Configuração de armazenamento de traces
├── docker-compose.yml
└── .env                       # Variáveis de ambiente (não commitado)
```

## Repositórios Relacionados

- **[josemanzoli/python-api](https://github.com/josemanzoli/python-api)** — Repositório da aplicação usada neste laboratório. Contém a lógica de negócio, instrumentação OTel e modelos SQL.

## ⚠️ Limitações conhecidas

### cAdvisor no macOS
Devido às diferenças no funcionamento do Docker Desktop para macOS e Linux, o serviço cAdvisor pode não funcionar corretamente em sistemas macOS. Isso ocorre porque o cAdvisor depende de acesso direto a caminhos do sistema Linux como `/sys`, `/dev/disk` e `/dev/kmsg`, que não estão disponíveis da mesma forma no macOS.

**Impacto**: Métricas de uso de CPU e RAM por container podem não estar disponíveis no painel do Grafana, mas o restante da stack (logs, traces, métricas de aplicação) funciona normalmente.

**Solução para usuários macOS**: Se você está usando macOS e deseja evitar mensagens de erro relacionadas ao cAdvisor, tem duas opções:

1. **Desativar completamente o cAdvisor** (recomendado para focar nos conceitos principais do lab):
   Crie um arquivo `docker-compose.override.yml` com o seguinte conteúdo:
   ```yaml
   services:
     cadvisor:
       # Esta substituição de comando efetivamente desativa o serviço
       command: ["sh", "-c", "echo 'cAdvisor intencionalmente desativado no macOS'; sleep infinity"]
   ```

2. **Tentar uma configuração mínima** (pode funcionar parcialmente em algumas versões do Docker Desktop):
   ```yaml
   services:
     cadvisor:
       image: gcr.io/cadvisor/cadvisor:latest
       container_name: cadvisor
       ports:
         - "8080:8080"
       volumes:
         - /var/run/docker.sock:/var/run/docker.sock:ro
         - /var/lib/docker/:/var/lib/docker:ro
       # Remover mounts problemáticos: /sys, /dev/disk, /dev/kmsg e privileged: true
   ```

> **Nota**: O foco principal deste laboratório é a observabilidade de aplicação (logs, traces, métricas de negócio). Mesmo sem o cAdvisor, você ainda poderá explorar todos os conceitos centrais usando:
> - Métricas de aplicação via Prometheus (`http_requests_total`, `messages_published_total`, etc.)
> - Logs centralizados com Loki e Grafana
> - Traces distribuídos com Tempo
> - Health checks e circuit breaker

## Créditos

## License

[MIT](LICENSE)