# Руководство Для Агентов И Разработчиков

Этот файл содержит обязательные правила изменения проекта `the-perepilitsa-assistant`. Перед реализацией нового модуля или изменением существующего кода необходимо прочитать документ полностью.

## Цели Проекта

- Асинхронная работа без блокировки Telegram polling.
- Явное разделение домена, бизнес-логики и Telegram transport.
- Предсказуемый lifecycle модулей и фоновых задач.
- Явная конфигурация только через переменные окружения.
- Типизированный код, покрытый тестами и всеми quality gates.
- Минимальные изменения без лишних абстракций и compatibility-кода.

## Технологический Стек

- Python 3.14.
- `aiogram` 3 для Telegram.
- `pydantic` и `pydantic-settings` для моделей и конфигурации.
- `httpx` для асинхронных HTTP-запросов.
- `uv` для зависимостей и запуска команд.
- `ruff`, `ty`, `pytest` для контроля качества.
- Docker Compose для dev/prod запуска.

## Архитектурные Слои

Каждый функциональный модуль должен быть разделён на три слоя.

### `src/core/<module>`

Содержит контракты и доменные структуры, не зависящие от runtime и Telegram:

- `config.py`: settings-класс модуля;
- `models.py`: Pydantic-модели и доменные типы;
- `client.py`: `Protocol` внешнего клиента;
- чистые функции, enum и типы, если они действительно нужны.

В `core` запрещены:

- импорты `aiogram`;
- Telegram HTML-тексты и клавиатуры;
- конкретные HTTP-клиенты и SDK;
- создание задач, файлов, сетевых соединений;
- wiring приложения.

### `src/logic/<module>`

Содержит реализацию и бизнес-логику:

- `service.py`: основной сценарий и правила предметной области;
- `client.py`: конкретный адаптер протокола из `core`;
- `store.py`: хранение состояния;
- `module.py`: lifecycle и владение фоновыми задачами;
- `__init__.py`: публичные runtime-компоненты.

Сервис должен принимать доменные значения и возвращать доменные результаты. Telegram-события, клавиатуры и форматирование не должны попадать в сервис.

Допустимое исключение: `module.py` является composition boundary и может импортировать factory Telegram router, чтобы выполнить контракт `BotModule`.

### `src/api/telegram`

Содержит Telegram transport:

- handlers сообщений и callback query;
- filters и типизированные `CallbackData`;
- клавиатуры;
- Telegram HTML-тексты;
- преобразование результата сервиса в Telegram-ответ.

Handlers должны быть тонкими: разобрать событие, вызвать сервис, отправить или изменить сообщение. Бизнес-сравнения, state и внешние API-запросы внутри handler запрещены.

## Эталонная Структура Модуля

```text
src/
├── core/<module>/
│   ├── __init__.py
│   ├── client.py
│   ├── config.py
│   └── models.py
├── logic/<module>/
│   ├── __init__.py
│   ├── client.py
│   ├── module.py
│   ├── service.py
│   └── store.py
└── api/telegram/
    └── <module>.py
```

Создавать каждый файл необязательно. Не добавляйте пустые абстракции: `store.py` нужен только при наличии state, `client.py` только при интеграции с внешней системой.

## Контракт Модуля

Модуль должен реализовывать `BotModule` из `src/logic/modules/base.py`:

```python
class ExampleModule:
    def router(self) -> Router: ...
    async def startup(self) -> None: ...
    async def shutdown(self) -> None: ...
```

Правила lifecycle:

- `startup()` открывает ресурсы, восстанавливает state и запускает долгоживущие задачи.
- `shutdown()` отменяет и ожидает все задачи, затем закрывает клиенты и другие ресурсы.
- Модуль обязан владеть всеми созданными им background tasks.
- Нельзя хранить task-set только в closure router, если module не может остановить эти задачи.
- `asyncio.CancelledError` нельзя проглатывать.
- Модули завершаются registry в обратном порядке регистрации.
- Повторный shutdown по возможности должен быть безопасным.

## Конфигурация

Для каждого settings-класса обязателен собственный `env_prefix`:

```python
class ExampleConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EXAMPLE_",
        extra="ignore",
        frozen=True,
    )

    api_url: str
    timeout_seconds: float = Field(gt=0)
```

Это автоматически создаёт имена `EXAMPLE_API_URL` и `EXAMPLE_TIMEOUT_SECONDS`.

Обязательные правила:

- У config-полей нет defaults.
- Не использовать `AliasChoices` и `validation_alias` для ручного имени env.
- Все переменные указываются явно в `.env.example`.
- Nullable-поле тоже обязательно; отключение задаётся пустой строкой и нормализуется validator-ом.
- Секреты задаются через `SecretStr`.
- Числовые интервалы, лимиты и TTL должны иметь ограничения `gt=0` или другие подходящие границы.
- Settings загружаются через `load_settings()` из `src/core/app`.
- Новый config создаётся в `src/main.py` и передаётся в `ApplicationContext.from_configs()`.
- Никогда не добавлять реальные секреты в `.env.example`, README, тесты или git.

## Dependency Wiring

Создание concrete client, store и service выполняется только в `src/logic/app/context.py`.

```python
example_client = HttpExampleClient(...)
example_store = ExampleStore(...)
example_service = ExampleService(client=example_client, store=example_store)
```

Дальнейшие шаги:

1. Добавить config и service в `ApplicationContext`.
2. Добавить сервис в dispatcher context в `src/logic/app/factory.py`:

```python
dispatcher["example_service"] = context.example_service
```

3. Зарегистрировать module в `create_module_registry()`.
4. Feature routers должны находиться между common router и fallback router.
5. Fallback router всегда регистрируется последним.

Не использовать глобальный service locator или скрытый DI-контейнер.

## Асинхронность И Внешние Интеграции

- Для HTTP использовать долгоживущий `httpx.AsyncClient`, а не новый клиент на каждый запрос.
- HTTP-клиент должен иметь явный `close()` и закрываться в module lifecycle.
- Таймаут обязателен и приходит из config.
- Cookies/session state должны сохраняться внутри клиента, если API этого требует.
- Синхронные тяжёлые операции запускать через `asyncio.to_thread()`.
- `asyncio.to_thread()` не останавливает worker thread при отмене coroutine; для долгих задач предусмотреть cooperative cancellation или graceful shutdown.
- Не создавать неограниченное число fire-and-forget tasks.
- Задача должна храниться владельцем и быть ожидаема при shutdown.
- Не блокировать event loop вызовами `time.sleep`, синхронным HTTP или тяжёлой обработкой.

## State И Хранилища

- In-memory store с обычными dictionary-операциями должен иметь синхронный API.
- Асинхронный API нужен только при реальном I/O или синхронизации.
- Файловые операции выполнять через `asyncio.to_thread()` на уровне сервиса.
- Persistent state записывать атомарно: временный файл, flush/fsync, `os.replace`.
- Повреждённый state должен обрабатываться безопасно и не ломать запуск бота.
- Изменение scope state, например города, не должно сравниваться со snapshot другого scope.
- Runtime-данные контейнера должны находиться в `.runtime` и при необходимости монтироваться в named volume.

## Telegram API

- Для callback payload использовать `CallbackData`, не ручной split строк.
- Callback query всегда подтверждать через `callback_query.answer()`.
- Пользовательские динамические значения экранировать для HTML parse mode.
- Ошибки удаления/редактирования уже удалённого сообщения можно подавлять через `TelegramBadRequest`.
- Не подавлять произвольный `Exception` без явной причины и логирования.
- Команды и callback должны проверять устаревшее состояние и давать понятный ответ.
- Повторное нажатие кнопки не должно запускать одну операцию дважды или оставлять зависшие progress-сообщения.
- Доступ ко всем feature routers проходит через `AllowedUserMiddleware`; модель доступа default-deny.

## Стиль Кода

- Не использовать `from __future__ import annotations`.
- Использовать современный синтаксис Python 3.14: `X | None`, встроенные generics, `type` aliases, type parameters.
- Логгер модуля называется `logger = logging.getLogger(__name__)`.
- Имена config/client/service/module следуют шаблону `FeatureConfig`, `FeatureClient`, `FeatureService`, `FeatureModule`.
- Concrete adapter получает уточняющий префикс: `HttpGpnClient`, `YtDlpYoutubeClient`.
- Protocol находится в `core`, concrete adapter в `logic`.
- Публичные package exports объявляются через `__all__`.
- Не добавлять compatibility-код без существующих внешних потребителей или persisted legacy format.
- Не дублировать parsers и форматтеры; общий dependency-free код выносить в подходящий `core` helper.
- Не делать функцию async, если в ней нет I/O, ожидания или async-контракта.
- Комментарии добавлять только для неочевидных решений.
- Предпочитать минимальное корректное изменение.

## Ошибки И Логирование

- Third-party исключения преобразовывать в доменные исключения на границе adapter-а.
- Handler не должен импортировать исключения concrete adapter-а.
- Ошибка фонового poller логируется и не завершает весь бот.
- `CancelledError` всегда пробрасывается дальше.
- Cleanup выполнять через `try/finally`.
- Ошибка cleanup одного ресурса не должна оставлять критичные внешние сессии открытыми.
- Не логировать токены, cookies, пароли и содержимое `SecretStr`.

## Тестирование

Минимальный набор для нового модуля:

- config: обязательность полей, env prefix, validators;
- client: успешный ответ, HTTP-ошибка, parsing и session/cookie behavior;
- store: save/load/claim/expiration и повреждённое состояние;
- service: основной flow, граничные условия и отсутствие ложных переходов;
- Telegram API: команды, callbacks, клавиатуры, экранирование и stale state;
- module: startup, background task, cancellation, shutdown и close;
- failure paths: внешняя ошибка, Telegram error, cancellation.

Тесты должны быть детерминированными:

- использовать `Event`, а не произвольный `sleep`;
- не обращаться к реальной сети;
- не читать рабочий `.env` в unit-тестах;
- использовать `httpx.MockTransport` для HTTP;
- временные файлы создавать через `tmp_path`.

## Обязательные Проверки

После любого нетривиального изменения выполнить:

```bash
uv run ruff check src tests pyproject.toml
uv run ruff format --check src tests pyproject.toml
uv run ty check
uv run pytest
```

Или:

```bash
make quality
```

При изменении Docker Compose дополнительно выполнить:

```bash
docker compose config --quiet
```

Нельзя считать задачу завершённой, если хотя бы одна проверка не прошла.

## Чек-Лист Нового Модуля

1. Определены доменные модели и protocol в `src/core/<module>`.
2. Config использует собственный prefix и не содержит defaults/aliases.
3. Concrete adapter находится в `src/logic/<module>/client.py`.
4. Бизнес-логика находится в service, а не handler/module.
5. Telegram handlers находятся в `src/api/telegram`.
6. Background tasks принадлежат module и закрываются в shutdown.
7. Клиенты и runtime state собираются в `ApplicationContext`.
8. Service добавлен в dispatcher context.
9. Module зарегистрирован перед fallback router.
10. `.env.example` содержит все новые переменные.
11. README описывает пользовательскую возможность и запуск, если они изменились.
12. Добавлены unit-тесты всех слоёв и failure paths.
13. Ruff, format, ty, pytest и Compose validation проходят.

## Запрещённые Решения

- `from __future__ import annotations`.
- Defaults в settings-классах.
- `AliasChoices`/`validation_alias` вместо `env_prefix`.
- `aiogram` и Telegram HTML в `core`.
- Сетевые запросы или сложная бизнес-логика в handlers.
- Новый HTTP client на каждый poll.
- Fire-and-forget task без владельца и shutdown.
- Broad `except Exception: pass`.
- Синхронный I/O в event loop.
- Ручное редактирование lockfile.
- Реальные токены и cookies в tracked-файлах.
- Изменение чужого или несвязанного кода без необходимости.
