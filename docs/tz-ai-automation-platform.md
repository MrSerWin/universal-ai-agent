# Техническое задание: Aimatica

> **Продукт:** Aimatica — AI Automation Platform
> **Домен:** aimatica.app
> **Версия:** 1.0 | Дата: 2026-03-30
> **Статус:** Draft

---

## 1. Описание продукта

### 1.1 Концепция

**Aimatica** — платформа для создания AI-автоматизаций бизнес-процессов. Пользователь собирает workflow из готовых блоков (триггер → AI-обработка → действие), подключает свои сервисы (Shopify, email, CRM) и запускает автоматизации без кода.

### 1.2 Эволюция продукта

| Фаза | Срок | Модель | Описание |
|------|------|--------|----------|
| Phase 1 | Месяцы 1-3 | Agency tool | Внутренний инструмент. Ты строишь автоматизации для клиентов. Клиенты видят результат, не платформу |
| Phase 2 | Месяцы 4-8 | Managed platform | Клиенты получают дашборд. Ты строишь автоматизации, клиенты мониторят |
| Phase 3 | Месяцы 9-14 | Self-serve SaaS | Пользователи строят автоматизации сами. Visual builder. Shopify App Store. Биллинг |

### 1.3 Первая вертикаль: Shopify

Почему Shopify:
- 2M+ активных магазинов ищут приложения в App Store
- Встроенная дистрибуция (не нужен PR/sales)
- Встроенный биллинг (Shopify Billing API)
- Понятные use-cases: описания товаров, категоризация заказов, email-автоматизации

### 1.4 Целевая аудитория

| Сегмент | Фаза | Что получает | Цена |
|---------|------|-------------|------|
| Малый e-commerce (Shopify) | Phase 2-3 | AI-описания, авто-теги, email | $29-99/мес |
| Средний бизнес | Phase 1-2 | Кастомные AI-автоматизации | $500-2000 setup + $100-300/мес |
| Агентства | Phase 3 | White-label платформа для клиентов | $199-499/мес |

---

## 2. Функциональные требования

### 2.1 Core: Движок автоматизаций

#### 2.1.1 Workflow (автоматизация)

Workflow — направленный ациклический граф (DAG) из шагов.

**Обязательные поля:**
- `id` — UUID
- `tenant_id` — владелец
- `name` — название
- `trigger_type` — тип триггера
- `trigger_config` — конфигурация триггера (JSON)
- `steps` — массив шагов (JSON DAG)
- `is_active` — включен/выключен
- `version` — версия (для отката)

**Операции:**
- CRUD (создание, чтение, обновление, удаление)
- Активация/деактивация
- Ручной запуск
- Просмотр истории запусков
- Клонирование
- Импорт/экспорт (JSON)

#### 2.1.2 Типы триггеров

| Триггер | Описание | Конфигурация |
|---------|----------|-------------|
| `webhook` | Входящий HTTP-запрос | URL path, метод, секрет для подписи |
| `schedule` | Расписание (cron) | Cron-выражение, timezone |
| `shopify_event` | Событие в Shopify | Тип события (orders/create, products/update, и т.д.) |
| `manual` | Ручной запуск | Схема входных данных |
| `api` | Вызов через API | API key + endpoint |

#### 2.1.3 Типы шагов

| Шаг | Описание | Параметры |
|-----|----------|-----------|
| `ai_completion` | Вызов LLM | Провайдер, модель, промпт-шаблон, max_tokens, temperature |
| `transform` | Трансформация данных | Jinja2-шаблон или JSONPath-выражение |
| `condition` | Ветвление | Выражение, ветки true/false |
| `http_request` | HTTP-запрос | URL, метод, headers, body (шаблоны) |
| `shopify_action` | Действие в Shopify | Тип действия, параметры |
| `delay` | Пауза | Длительность |
| `loop` | Итерация | Массив, подшаги для каждого элемента |
| `code` | Кастомный код | Sandboxed Python/JS (Phase 3) |

#### 2.1.4 Workflow Run (запуск)

Каждый запуск workflow создаёт запись:
- `id`, `workflow_id`, `tenant_id`
- `status`: pending → running → completed / failed / cancelled
- `trigger_data` — данные, которые запустили workflow
- `started_at`, `completed_at`
- `error` — текст ошибки (если failed)

Каждый шаг в запуске создаёт step_run:
- `step_id`, `step_type`, `status`
- `input_data`, `output_data`
- `tokens_used`, `duration_ms`
- `error`

#### 2.1.5 Исполнение

- Шаги выполняются в топологическом порядке DAG
- Независимые ветки могут выполняться параллельно (Phase 3)
- Выход одного шага доступен как переменная в следующих: `{{ step_name.output }}`
- Ошибка в шаге → retry (экспоненциальный backoff, настраиваемый) → если исчерпаны попытки → run = failed
- Таймаут на шаг: настраиваемый, по умолчанию 30 секунд (AI — 120 секунд)
- Таймаут на весь run: 10 минут

### 2.2 AI-интеграция

#### 2.2.1 Поддерживаемые провайдеры

| Провайдер | Модели | Приоритет |
|-----------|--------|-----------|
| Anthropic | Claude Haiku, Sonnet, Opus | Primary |
| OpenAI | GPT-4o, GPT-5-mini | Secondary |
| Ollama | Qwen, Llama (локальные) | Fallback / dev |

#### 2.2.2 Абстракция провайдеров

Единый интерфейс для всех провайдеров:
```
complete(messages, config) → CompletionResult
stream(messages, config) → AsyncIterator[str]
```

Конфигурация на уровне тенанта:
- Какие провайдеры доступны
- API ключи (зашифрованные)
- Дефолтная модель
- Fallback-цепочка: Claude → OpenAI → Ollama

#### 2.2.3 Роутинг моделей

Автоматический выбор модели по задаче:
- Простые задачи (классификация, извлечение) → Haiku / GPT-5-mini
- Средние (генерация текста, ревью) → Sonnet / GPT-4o
- Сложные (архитектура, длинные рассуждения) → Opus

#### 2.2.4 Prompt Templates

- Jinja2-шаблоны с переменными из контекста workflow
- Системный промпт + пользовательский промпт
- Формат вывода: text, JSON (structured output), markdown
- Учёт бюджета токенов (автоматическое сокращение контекста)

#### 2.2.5 Трекинг использования

Каждый AI-вызов записывает:
- provider, model
- input_tokens, output_tokens
- latency_ms
- cost_usd (рассчитывается по тарифам провайдера)

### 2.3 Shopify App

#### 2.3.1 Установка

1. Продавец находит приложение в Shopify App Store
2. Клик "Install" → OAuth-авторизация
3. Приложение получает access token → зашифрованное хранение
4. Регистрация обязательных GDPR-вебхуков
5. Регистрация вебхуков для автоматизаций
6. Показ embedded UI в Shopify Admin

#### 2.3.2 Shopify Actions

| Действие | GraphQL mutation | Описание |
|----------|-----------------|----------|
| Добавить тег клиенту | `tagsAdd` | Сегментация |
| Обновить товар | `productUpdate` | AI-описания, SEO |
| Создать скидку | `discountCodeBasicCreate` | Промо-автоматизации |
| Обновить метаполе | `metafieldsSet` | Произвольные данные |
| Отправить уведомление | External API (SendGrid) | Email-автоматизации |

#### 2.3.3 Готовые шаблоны автоматизаций

| Шаблон | Триггер | Что делает |
|--------|---------|-----------|
| AI Product Descriptions | Manual / bulk | Фото + название → SEO-описание на нужном языке |
| Order Categorization | orders/create | AI классифицирует заказ → теги + роутинг |
| Customer Segmentation | customers/create | AI анализирует → VIP/standard/risk тег |
| Review Response | External webhook | AI генерирует ответ на отзыв в тоне бренда |
| Abandoned Cart Email | checkouts/update | AI персонализирует email для возврата |
| Inventory Alert | products/update | Уведомление когда запас ниже порога |

#### 2.3.4 Embedded UI (Shopify Admin)

Встроенное приложение в админке Shopify (iframe + App Bridge):
- **Dashboard** — активные автоматизации, последние запуски, использование AI
- **Automations** — список, включение/выключение, настройка
- **Run History** — логи запусков с деталями по шагам
- **Settings** — AI-провайдер, язык описаний, тон бренда
- **Billing** — текущий план, использование, upgrade

Технология: React + Shopify Polaris (официальная UI-библиотека)

### 2.4 Dashboard (веб-приложение)

#### 2.4.1 Страницы

| Страница | Описание | Фаза |
|----------|----------|:----:|
| `/login` | Вход через Clerk | 1 |
| `/dashboard` | Обзор: активные workflows, последние runs, usage | 1 |
| `/workflows` | Список автоматизаций | 1 |
| `/workflows/:id` | Детали workflow + история запусков | 1 |
| `/workflows/:id/runs/:runId` | Детали запуска (шаги, данные, ошибки) | 1 |
| `/workflows/new` | Создание workflow (форма, Phase 1; visual builder, Phase 3) | 1/3 |
| `/connections` | Подключённые сервисы (Shopify, email, etc.) | 2 |
| `/secrets` | Управление API-ключами и токенами | 2 |
| `/settings` | Настройки тенанта, AI-провайдеры, тон бренда | 2 |
| `/billing` | Текущий план, использование, оплата | 3 |
| `/team` | Участники команды, роли | 3 |
| `/api-keys` | Создание и управление API-ключами | 3 |
| `/templates` | Маркетплейс готовых шаблонов | 3 |
| `/builder` | Visual workflow builder (drag-and-drop DAG) | 3 |

#### 2.4.2 Real-time обновления

WebSocket-подключение для:
- Прогресс выполнения workflow (шаг за шагом)
- Уведомления об ошибках
- Обновление счётчика использования

### 2.5 Шаблоны (Templates)

Предустановленные workflows, которые можно установить в 1 клик:

**Категории:**
- E-commerce (Shopify)
- Customer Support
- Content Generation
- Data Processing
- Notifications

Каждый шаблон содержит:
- Название, описание, категория
- Workflow JSON (триггер + шаги)
- Список требуемых подключений (Shopify, email, etc.)
- Скриншоты / demo

### 2.6 API (для внешних интеграций)

#### 2.6.1 REST API v1

```
# Auth
POST   /api/v1/auth/token

# Workflows
GET    /api/v1/workflows
POST   /api/v1/workflows
GET    /api/v1/workflows/:id
PUT    /api/v1/workflows/:id
DELETE /api/v1/workflows/:id
POST   /api/v1/workflows/:id/execute

# Runs
GET    /api/v1/workflows/:id/runs
GET    /api/v1/runs/:id
POST   /api/v1/runs/:id/cancel

# AI (прямой доступ)
POST   /api/v1/ai/complete

# Shopify
GET    /api/v1/shopify/connections
POST   /api/v1/shopify/connect
DELETE /api/v1/shopify/connections/:id

# Secrets
GET    /api/v1/secrets
POST   /api/v1/secrets
DELETE /api/v1/secrets/:name

# Usage
GET    /api/v1/usage/summary
GET    /api/v1/usage/history

# Webhooks (входящие)
POST   /api/v1/webhooks/:path
POST   /api/v1/shopify/webhooks
```

#### 2.6.2 WebSocket

```
WS /api/v1/ws

События:
  workflow.run.started
  workflow.run.step_completed
  workflow.run.completed
  workflow.run.failed
```

#### 2.6.3 Аутентификация API

- Dashboard: Clerk JWT в cookie/header
- External API: API key в header `Authorization: Bearer aap_live_xxx`
- Shopify webhooks: HMAC-SHA256 подпись в header
- Public webhooks: секрет в query string или header

---

## 3. Нефункциональные требования

### 3.1 Производительность

| Метрика | Требование |
|---------|-----------|
| API response time (p95) | < 200ms |
| Webhook processing start | < 2 секунды после получения |
| AI completion (p95) | < 30 секунд |
| Workflow execution (простой, 3-5 шагов) | < 60 секунд |
| Dashboard page load | < 2 секунды |
| Concurrent workflows per tenant | До 10 |
| Shopify App embedded UI load | < 500ms (Shopify requirement) |

### 3.2 Надёжность

| Метрика | Требование |
|---------|-----------|
| Uptime | 99.5% (допускается ~3.6 часа простоя/мес) |
| Data durability | 99.99% (PostgreSQL backups) |
| Webhook delivery | At-least-once (идемпотентная обработка) |
| Failed workflow retry | До 3 попыток с exponential backoff |
| Queue message loss | 0 (Redis persistence + acknowledgment) |

### 3.3 Масштабируемость

| Фаза | Тенанты | Runs/день | AI calls/день |
|------|:-------:|:---------:|:-------------:|
| Phase 1 | 1-10 | 100 | 500 |
| Phase 2 | 10-100 | 5,000 | 25,000 |
| Phase 3 | 100-1,000 | 50,000 | 250,000 |

Горизонтальное масштабирование через:
- Добавление worker-процессов
- Redis queue partitioning
- Read replicas для PostgreSQL

### 3.4 Безопасность

#### 3.4.1 Аутентификация и авторизация

- Clerk для аутентификации (JWT, OAuth, MFA)
- Роли: owner, admin, member, viewer
- Каждый API-запрос проходит: Auth → Tenant Resolution → RLS Context → Handler
- API ключи: bcrypt hash, prefix для идентификации, scopes, expiration

#### 3.4.2 Изоляция данных (Multi-tenant)

- PostgreSQL Row Level Security (RLS) на ВСЕХ таблицах с tenant_id
- Каждое соединение с БД устанавливает `SET app.current_tenant_id = X`
- Интеграционные тесты: создать 2 тенанта, убедиться что нет cross-access
- Никогда не доверять tenant_id из клиента — только из JWT/API key

#### 3.4.3 Хранение секретов

- API ключи провайдеров шифруются AES-256-GCM
- Ключ шифрования — per-tenant, derived от master key
- Master key — переменная окружения (Phase 1), KMS (Phase 3)
- Секреты никогда не возвращаются в API-ответах (только имена)
- Секреты доступны в workflow через `{{ secrets.name }}` — резолвятся на сервере, не на клиенте

#### 3.4.4 Безопасность Webhook

- Shopify: HMAC-SHA256 верификация каждого входящего вебхука
- Custom webhooks: секрет в конфигурации, проверка подписи
- Rate limiting: 100 req/min на endpoint на тенанта
- Payload size limit: 5MB

#### 3.4.5 Sandbox для кастомного кода (Phase 3)

- Deno isolates (V8 sandbox)
- Нет доступа к файловой системе, сети, env vars (по умолчанию)
- CPU limit: 100ms
- Memory limit: 128MB
- Timeout: 10 секунд

#### 3.4.6 GDPR / Data Protection

- Shopify GDPR webhooks (обязательные):
  - `customers/data_request` — экспорт данных клиента
  - `customers/redact` — удаление данных клиента
  - `shop/redact` — удаление данных магазина
- Право на удаление: удаление тенанта каскадно удаляет все данные
- Логи workflow runs хранятся 90 дней, потом автоматическое удаление
- Нет хранения PII в логах (маскирование email, phone)

### 3.5 Мониторинг

| Компонент | Инструмент | Что отслеживаем |
|-----------|-----------|-----------------|
| Ошибки | Sentry | Exceptions, stack traces, user context |
| Логи | Axiom | Structured JSON logs, traces |
| Uptime | BetterStack | API endpoints, health checks |
| БД | Neon Dashboard | Query performance, connections |
| Очереди | Upstash Console | Queue depth, processing rate |
| AI usage | Custom dashboard | Tokens, cost, latency per provider |

**Алерты:**
- API error rate > 5% за 5 минут → Telegram/Slack
- Queue depth > 1000 → email
- AI provider down → auto-failover + alert
- Workflow failure rate > 20% для тенанта → email тенанту

---

## 4. Архитектура системы

### 4.1 Общая схема

```
┌─────────────────────────────────────────────────────────┐
│                 Cloudflare (CDN + WAF + DNS)              │
└─────────┬───────────────────────────────┬────────────────┘
          │                               │
┌─────────▼──────────┐    ┌──────────────▼──────────────┐
│   Web App          │    │   API Gateway               │
│   Next.js (Vercel) │    │   Hono (Fly.io)             │
│                    │    │                             │
│   Dashboard        │    │   Auth (Clerk JWT)          │
│   Workflow Builder │    │   Rate limiting             │
│   Settings         │    │   Tenant resolution         │
└────────────────────┘    │   Request validation        │
                          └──────┬──────────┬───────────┘
                                 │          │
                    ┌────────────▼──┐  ┌────▼────────────┐
                    │ Shopify App   │  │ Webhook Ingress  │
                    │ Service (TS)  │  │ (Hono)           │
                    │               │  │                  │
                    │ OAuth flow    │  │ HMAC verify      │
                    │ Shopify API   │  │ Route to queue   │
                    │ Polaris UI    │  │                  │
                    └───────┬───────┘  └────────┬─────────┘
                            │                   │
                    ┌───────▼───────────────────▼──────────┐
                    │       Message Queue (BullMQ/Redis)    │
                    │                                       │
                    │  workflow.execute    ai.completion     │
                    │  shopify.sync       webhook.process    │
                    │  billing.usage      notifications      │
                    └──────────────────┬────────────────────┘
                                       │
                    ┌──────────────────▼────────────────────┐
                    │          Worker Pool                   │
                    │                                       │
                    │  ┌───────────────┐ ┌───────────────┐ │
                    │  │ Workflow      │ │ AI Worker     │ │
                    │  │ Executor (Py) │ │ (Python)      │ │
                    │  │               │ │               │ │
                    │  │ DAG execution │ │ Claude API    │ │
                    │  │ Retry logic   │ │ OpenAI API    │ │
                    │  │ State mgmt    │ │ Ollama        │ │
                    │  └───────────────┘ │ Fallback      │ │
                    │                    └───────────────┘ │
                    │  ┌───────────────┐ ┌───────────────┐ │
                    │  │ Shopify       │ │ Billing       │ │
                    │  │ Worker (TS)   │ │ Worker (TS)   │ │
                    │  │               │ │               │ │
                    │  │ Product sync  │ │ Usage agg     │ │
                    │  │ Order hooks   │ │ Stripe meter  │ │
                    │  └───────────────┘ └───────────────┘ │
                    └──────────────────────────────────────┘
                                       │
                    ┌──────────────────▼────────────────────┐
                    │             Data Layer                 │
                    │                                       │
                    │  PostgreSQL (Neon)  — RLS-изоляция    │
                    │  Redis (Upstash)   — очереди, кэш    │
                    │  Cloudflare R2     — файлы            │
                    └──────────────────────────────────────┘
```

### 4.2 Стек технологий

| Слой | Технология | Обоснование |
|------|-----------|-------------|
| Frontend | Next.js 15 (Vercel) | React, SSR, zero-ops deploy |
| API Gateway | Hono (Fly.io) | Лёгкий, fast, TypeScript, без cold starts |
| Shopify Service | TypeScript + @shopify/shopify-api | Официальная библиотека |
| Workflow Engine | Python (FastAPI workers) | LLM-библиотеки Python-first, твой существующий код |
| AI Layer | Python (anthropic, openai SDK) | Нативные SDK провайдеров |
| Database | PostgreSQL (Neon) | Serverless, branching, RLS, scale-to-zero |
| Queue | BullMQ + Redis (Upstash) | Retries, priorities, cron, serverless Redis |
| Auth | Clerk | Multi-tenant, MFA, organizations, бесплатно до 10K MAU |
| Billing | Stripe + Shopify Billing API | Usage-based metering, Shopify для магазинов |
| Monitoring | Sentry + Axiom + BetterStack | Errors + logs + uptime |
| Storage | Cloudflare R2 | S3-совместимый, без egress fees |
| CDN | Cloudflare | Бесплатный план |

### 4.3 Структура монорепозитория

```
aimatica/
├── apps/
│   ├── web/                    # Next.js dashboard (Vercel)
│   │   ├── app/                # App Router pages
│   │   ├── components/         # React компоненты
│   │   └── lib/                # Клиентские утилиты
│   ├── api/                    # Hono API gateway (Fly.io)
│   │   ├── src/
│   │   │   ├── routes/         # API routes
│   │   │   ├── middleware/     # Auth, tenant, rate-limit
│   │   │   └── index.ts        # Entry point
│   │   └── Dockerfile
│   └── shopify/                # Shopify App (Fly.io)
│       ├── src/
│       │   ├── auth.ts         # OAuth flow
│       │   ├── webhooks.ts     # Webhook handlers
│       │   └── ui/             # Polaris embedded UI
│       └── Dockerfile
├── packages/
│   ├── db/                     # Drizzle ORM schema + migrations
│   │   ├── schema.ts           # Все таблицы
│   │   ├── migrations/         # SQL-миграции
│   │   └── seed.ts             # Тестовые данные
│   ├── auth/                   # Clerk helpers, middleware
│   ├── queue/                  # BullMQ job definitions + types
│   ├── shared/                 # Общие типы, утилиты
│   └── ui/                     # Shared React компоненты
├── workers/
│   ├── engine/                 # Python: workflow executor
│   │   ├── executor.py         # DAG executor
│   │   ├── steps/              # Step type implementations
│   │   │   ├── ai_completion.py
│   │   │   ├── http_request.py
│   │   │   ├── transform.py
│   │   │   ├── condition.py
│   │   │   ├── shopify_action.py
│   │   │   └── delay.py
│   │   └── Dockerfile
│   ├── ai/                     # Python: AI provider layer
│   │   ├── providers/
│   │   │   ├── base.py         # Protocol/interface
│   │   │   ├── anthropic.py    # Claude
│   │   │   ├── openai.py       # GPT
│   │   │   └── ollama.py       # Локальные модели
│   │   ├── router.py           # Model selection
│   │   ├── prompts.py          # Template engine
│   │   └── tracker.py          # Usage tracking
│   └── bridge/                 # TS: BullMQ ↔ Python bridge
├── tests/
│   ├── unit/                   # Unit тесты
│   ├── integration/            # Интеграционные (с БД)
│   └── e2e/                    # End-to-end
├── infra/
│   ├── fly.toml
│   ├── docker/
│   └── scripts/
├── turbo.json
├── pnpm-workspace.yaml
└── pyproject.toml
```

---

## 5. Схема базы данных

### 5.1 ER-диаграмма

```
tenants ──────────┐
  │                │
  ├── tenant_memberships ── users (Clerk)
  │
  ├── workflows
  │     └── workflow_runs
  │           └── step_runs
  │
  ├── secrets
  │
  ├── shopify_connections
  │
  ├── usage_events
  │
  └── api_keys
```

### 5.2 Изоляция тенантов (RLS)

Каждая таблица с `tenant_id`:
1. `ALTER TABLE xxx ENABLE ROW LEVEL SECURITY;`
2. `CREATE POLICY tenant_isolation ON xxx USING (tenant_id = current_setting('app.current_tenant_id')::UUID);`
3. Каждый запрос к БД: `SET app.current_tenant_id = '<uuid>'`

### 5.3 Шифрование секретов

- Алгоритм: AES-256-GCM
- Per-tenant encryption key = HKDF(master_key, tenant_id)
- Master key → env var `ENCRYPTION_MASTER_KEY`
- При ротации: re-encrypt все секреты, grace period для старого ключа

---

## 6. Биллинг и тарифные планы

### 6.1 Планы

| | Free | Starter ($29/мес) | Pro ($99/мес) | Enterprise |
|---|---|---|---|---|
| Workflows | 3 | 20 | Unlimited | Unlimited |
| Runs/мес | 100 | 5,000 | 50,000 | Custom |
| AI tokens/мес | 50K | 500K | 5M | Custom |
| Подключения | 1 | 5 | Unlimited | Unlimited |
| Участники | 1 | 3 | 10 | Unlimited |
| Поддержка | Community | Email | Priority | Dedicated |
| Templates | Basic | All | All + custom | All + custom |
| API access | Нет | Read-only | Full | Full |

### 6.2 Usage-based billing

Stripe Metered Subscriptions:
- Каждый час worker агрегирует usage_events → Stripe usage_records
- Если лимит плана превышен → уведомление + soft limit (запускаются, но предупреждаем)
- Hard limit на 150% от плана → workflow execution приостановлен

### 6.3 Shopify Billing

Для магазинов из Shopify App Store — оплата через Shopify:
- `appSubscriptionCreate` GraphQL mutation
- Shopify берёт 20% комиссию (первый $1M), потом 15%
- Учитывать комиссию при ценообразовании

---

## 7. Deployment и инфраструктура

### 7.1 Стоимость инфраструктуры

| Сервис | Phase 1 (0-10) | Phase 2 (10-100) | Phase 3 (100-1000) |
|--------|:--------------:|:----------------:|:------------------:|
| Vercel (frontend) | $0 | $20/мес | $20/мес |
| Fly.io (API + workers) | $5-15/мес | $30-50/мес | $100-200/мес |
| Neon (PostgreSQL) | $0 | $19/мес | $69/мес |
| Upstash (Redis) | $0 | $10/мес | $30/мес |
| Clerk (auth) | $0 | $0 | $25/мес |
| Cloudflare (CDN + R2) | $0 | $5/мес | $20/мес |
| Sentry | $0 | $26/мес | $26/мес |
| Axiom | $0 | $0 | $25/мес |
| Stripe | 2.9%+$0.30 | 2.9%+$0.30 | 2.9%+$0.30 |
| **Итого инфра** | **$5-15/мес** | **$110-130/мес** | **$315-415/мес** |
| **+ AI API costs** | **~$50/мес** | **~$500-1000/мес** | **~$5K-10K/мес** |

### 7.2 CI/CD

GitHub Actions:
1. PR: lint → typecheck → test (Turborepo cached)
2. Merge to main: auto-deploy
   - `apps/web` → Vercel
   - `apps/api` → Fly.io
   - `apps/shopify` → Fly.io
   - `workers/*` → Fly.io
3. DB migrations: GitHub Action → Neon

---

## 8. План реализации

### Phase 1: Agency Foundation (недели 1-6)

| Неделя | Задачи |
|--------|--------|
| 1-2 | Scaffold монорепо (Turborepo + pnpm + uv). DB schema (Neon + Drizzle + RLS). Auth (Clerk). API gateway skeleton (Hono). |
| 3-4 | Workflow модель + CRUD API. Sequential executor (Python). AI provider abstraction (Claude + OpenAI). BullMQ setup. Run logging. |
| 5-6 | Минимальный dashboard (список workflows, просмотр runs). Webhook триггер. HTTP request step. Deploy всего. **Первый клиент.** |

**Deliverable:** Работающая платформа для создания AI-автоматизаций. Ты строишь workflows через API/код, клиенты видят результат.

### Phase 2: Shopify Vertical (недели 7-12)

| Неделя | Задачи |
|--------|--------|
| 7-8 | Shopify OAuth flow. Webhook receiver + HMAC. Shopify connection management. Basic actions (tag, update product). |
| 9-10 | AI product descriptions workflow. Order categorization. Customer segmentation. Template library. |
| 11-12 | Embedded Shopify UI (Polaris). Run history в Shopify admin. Error notifications. **Подача в Shopify App Store.** |

**Deliverable:** Shopify App с AI-автоматизациями. Продавцы устанавливают из App Store.

### Phase 3: Self-Serve SaaS (недели 13-24)

| Неделя | Задачи |
|--------|--------|
| 13-16 | Visual workflow builder (React Flow). Step configuration panels. Test run. Template marketplace. |
| 17-20 | Stripe billing (subscriptions + metered). Shopify Billing API. Usage dashboard. Plan limits. Onboarding flow. |
| 21-24 | Parallel step execution. Workflow versioning. Team collaboration (Clerk Organizations). Public API + API keys. Documentation site. |

**Deliverable:** Полноценный SaaS. Пользователи строят автоматизации сами. Биллинг работает.

---

## 9. Критерии приёмки (Definition of Done)

### 9.1 Общие критерии

- [ ] Все API endpoints имеют тесты (unit + integration)
- [ ] RLS-изоляция подтверждена тестами (cross-tenant access невозможен)
- [ ] Все секреты зашифрованы, не появляются в логах
- [ ] Error handling на каждом уровне (API, workers, queue)
- [ ] Structured logging с tenant_id и correlation_id
- [ ] CI/CD pipeline работает (PR → test → merge → deploy)
- [ ] Документация API (OpenAPI spec)

### 9.2 Phase 1 критерии

- [ ] Можно создать workflow через API
- [ ] Workflow запускается по webhook
- [ ] AI completion step работает (Claude + OpenAI)
- [ ] HTTP request step работает
- [ ] Transform и condition steps работают
- [ ] Run history записывается с деталями по шагам
- [ ] Dashboard показывает workflows и runs
- [ ] Multi-tenant изоляция работает

### 9.3 Phase 2 критерии

- [ ] Shopify OAuth установка работает
- [ ] Shopify webhooks принимаются и обрабатываются
- [ ] AI product descriptions генерируются
- [ ] Embedded UI в Shopify Admin работает
- [ ] GDPR webhooks обрабатываются
- [ ] Shopify App Store review пройден

### 9.4 Phase 3 критерии

- [ ] Visual builder работает (создание workflow drag-and-drop)
- [ ] Stripe billing работает (подписки + usage metering)
- [ ] Shopify Billing работает
- [ ] API keys создаются и работают
- [ ] Rate limiting работает
- [ ] Team management работает
- [ ] Onboarding flow для нового пользователя

---

## 10. Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|:---------:|:-------:|-----------|
| Shopify App Store rejection | Средняя | Высокое | Следовать чеклисту с первого дня. GDPR webhooks обязательны. Тестировать на dev store. |
| AI provider outage | Средняя | Среднее | Fallback chain: Claude → OpenAI → Ollama. Circuit breaker. |
| RLS misconfiguration → data leak | Низкая | Критическое | Automated tests на cross-tenant isolation. Никогда не отключать RLS. |
| Queue backlog | Средняя | Среднее | Per-tenant rate limiting. Dead letter queue. Alert на глубину > 1000. |
| Solo dev bus factor | Высокая | Высокое | README, ADR, типизация, automated deploys. Код должен быть понятен через 6 месяцев. |
| Competitor copies features | Высокая | Среднее | Фокус на одной вертикали (Shopify). Скорость итерации > feature parity. |

---

## Приложение A: Глоссарий

| Термин | Определение |
|--------|------------|
| Tenant | Организация-клиент. Все данные привязаны к tenant |
| Workflow | Автоматизация: триггер + цепочка шагов |
| Run | Конкретный запуск workflow |
| Step | Один шаг в workflow (AI call, HTTP request, и т.д.) |
| DAG | Directed Acyclic Graph — структура workflow |
| RLS | Row Level Security — изоляция данных на уровне строк в PostgreSQL |
| Polaris | Официальная UI-библиотека Shopify для embedded apps |
| App Bridge | JS SDK Shopify для связи embedded app ↔ Shopify Admin |
