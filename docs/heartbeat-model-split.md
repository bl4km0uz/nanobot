# Разделение модели heartbeat и основной модели агента

Ниже — практичный план изменений в текущем коде nanobot, чтобы heartbeat использовал отдельную (более дешевую) модель, а основной диалог/инструменты — основную (более дорогую).

## Что есть сейчас (в коде)

1. `HeartbeatService` получает **один** `provider` и **один** `model`, затем использует их и для этапа `decide`, и для post-run `evaluate_response`.
2. В `cli/commands.py` heartbeat создается с `provider=provider` и `model=agent.model`, то есть тем же провайдером/моделью, что и основной агент.
3. В конфиге `HeartbeatConfig` нет отдельного поля для heartbeat-модели.

## Что изменить

### Шаг 1. Расширить конфиг heartbeat отдельным `model_override`

Файл: `nanobot/config/schema.py`

- В `HeartbeatConfig` добавить поле:
  - `model_override: str | None = Field(...)`
  - С alias-совместимостью как у dream (`heartbeat.model`, `heartbeat.modelOverride`, `heartbeat.model_override`).
- Пример:

```python
model_override: str | None = Field(
    default=None,
    validation_alias=AliasChoices("modelOverride", "model", "model_override"),
)
```

Зачем: это позволит явно указать дешевую модель только для heartbeat, не затрагивая `agents.defaults.model`.

### Шаг 2. Сделать фабрику провайдера для произвольной модели

Файл: `nanobot/nanobot.py`

- Обобщить `_make_provider(config)` до варианта, принимающего целевую модель, например:
  - `_make_provider(config, model_override: str | None = None)`.
- Внутри использовать `effective_model = model_override or config.agents.defaults.model`.
- Везде, где сейчас используется `model`, переключить на `effective_model`.

Зачем: чтобы heartbeat мог поднимать отдельный provider instance для своей модели (в т.ч. другого вендора), а не делить основной.

### Шаг 3. Пробросить отдельный heartbeat provider/model в запуске CLI

Файл: `nanobot/cli/commands.py`

- Перед созданием `HeartbeatService` вычислить:
  - `hb_model = hb_cfg.model_override or agent.model`
- Если `hb_cfg.model_override` задан:
  - создать `heartbeat_provider = _make_provider(config, model_override=hb_model)`
- Иначе:
  - `heartbeat_provider = provider` (обратная совместимость).
- Передать в `HeartbeatService`:
  - `provider=heartbeat_provider`
  - `model=hb_model`

Зачем: heartbeat decision и evaluate будут автоматически идти в дешевую модель, а `on_execute` продолжит исполняться через `agent.process_direct(...)` на основной модели.

### Шаг 4. Явно зафиксировать, что основной раннер не меняется

Файл: `nanobot/cli/commands.py`

- В `on_heartbeat_execute` оставить вызов через `agent.process_direct(...)` без изменения модели.
- (Опционально) добавить короткий комментарий: heartbeat LLM используется только для `decide/evaluate`, а выполнение задач — на основном агенте.

Зачем: это и есть требуемое разделение «cheap heartbeat / expensive main loop».

### Шаг 5. Документация конфигурации

Файл: `docs/configuration.md`

- В секции `gateway.heartbeat` добавить новое поле:
  - `modelOverride` (или `model`) — отдельная модель heartbeat.
- Добавить пример:

```json
{
  "agents": {
    "defaults": {
      "model": "openrouter/anthropic/claude-opus-4-5"
    }
  },
  "gateway": {
    "heartbeat": {
      "enabled": true,
      "intervalS": 1800,
      "modelOverride": "openai/gpt-4.1-mini"
    }
  }
}
```

### Шаг 6. Тесты

1. `tests/config/test_*`:
   - новый тест на парсинг `gateway.heartbeat.modelOverride` и legacy `gateway.heartbeat.model`.
2. `tests/agent/test_heartbeat_service.py`:
   - убедиться, что `_decide` и `evaluate_response` вызываются с heartbeat-моделью.
3. `tests/cli/test_commands.py`:
   - при `modelOverride` heartbeat создается с отдельным provider/model;
   - без override поведение прежнее.

## Минимальный rollout-план

1. Сначала влить изменения схемы + CLI wiring + тесты (без изменения поведения по умолчанию).
2. В прод-конфиге добавить `gateway.heartbeat.modelOverride` на дешевую модель.
3. Проверить логи старта (`Heartbeat: every ...`) и добавить лог текущей heartbeat-модели (рекомендуется).
4. Наблюдать 1–2 дня: частота heartbeat, стоимость, отсутствие деградации по уведомлениям.

## Результат после изменений

- Heartbeat `decide` + `evaluate`: дешевая модель.
- Основной агент (чат, tools, выполнение heartbeat-задач): дорогая модель.
- Backward compatibility: если `modelOverride` не задан — поведение как сейчас.
