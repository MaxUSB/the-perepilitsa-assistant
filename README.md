# The Perepilitsa Assistant

## Purpose

`the-perepilitsa-assistant` is a personal Telegram bot built on top of `aiogram` with a modular architecture.

Current goals of the project:

- keep the bot asynchronous end-to-end;
- isolate domain/configuration code from runtime wiring;
- make new bot features pluggable with minimal changes to existing modules;
- support local development and production deployment through Docker Compose;
- enforce project quality through linting, formatting, type checking, and tests.

Implemented feature modules:

- `YouTube Downloader` for interactive video downloads;
- `GPN` for background fuel availability monitoring and `/fuel` station lookup.

## Tech Stack

- Python `3.14.x`
- `uv` for dependency management and execution
- `aiogram` v3 for Telegram bot runtime
- `pydantic` v2 and `pydantic-settings` for models and environment-based config
- `yt-dlp` for YouTube metadata extraction and downloads
- `httpx` for asynchronous GPN API requests
- `ruff` for linting and formatting
- `ty` for type checking
- `pytest` and `pytest-asyncio` for tests
- Docker and Docker Compose for runtime environments

## Project Structure

```text
.
├── src/
│   ├── main.py
│   ├── api/
│   │   └── telegram/
│   ├── core/
│   │   ├── app/
│   │   ├── bot/
│   │   ├── gpn/
│   │   └── youtube/
│   └── logic/
│       ├── app/
│       ├── bot/
│       ├── gpn/
│       ├── modules/
│       └── youtube/
├── tests/
│   └── unit/
├── Dockerfile
├── docker-compose.yml
├── docker-compose.dev.yml
├── docker-compose.prod.yml
├── Makefile
├── pyproject.toml
└── TECHNICAL.md
```

## Architectural Layers

### `src/core`

`core` contains reusable, dependency-light application building blocks.

Typical contents:

- configuration classes;
- pydantic models;
- protocols and interfaces;
- utility functions;
- enums and custom types.

Important rule:

- `core` should not know how the application is bootstrapped;
- `core` describes structure and contracts, not runtime wiring.

Examples in the current codebase:

- `src/core/app/config.py` contains `AppConfig`;
- `src/core/bot/config.py` contains `BotConfig`;
- `src/core/youtube/models.py` contains YouTube data models;
- `src/core/youtube/client.py` contains the `YoutubeClient` protocol;
- `src/core/gpn/client.py` contains the `GpnClient` protocol;
- `src/core/gpn/models.py` contains station and fuel availability models.

### `src/logic`

`logic` contains runtime behavior and concrete implementations.

Typical responsibilities:

- instantiate services and clients;
- orchestrate application flows;
- implement module-specific business logic;
- manage in-memory stores or adapters;
- define module lifecycle hooks.

Examples in the current codebase:

- `src/logic/app/context.py` builds `ApplicationContext`;
- `src/logic/app/factory.py` builds the `Dispatcher` and module registry;
- `src/logic/youtube/client.py` implements the concrete `yt-dlp` adapter;
- `src/logic/youtube/service.py` implements the YouTube download flow;
- `src/logic/gpn/service.py` owns fuel state and comparison logic;
- `src/logic/gpn/store.py` persists the latest station snapshot.

### `src/api`

`api` is the transport-facing layer.

For this bot, that means Telegram handlers, filters, callback payloads, and router wiring.

The API layer should:

- parse incoming Telegram events;
- call application services from `logic`;
- avoid heavy business logic;
- stay thin and transport-oriented.

Examples:

- `src/api/telegram/common.py` handles `/start`;
- `src/api/telegram/fallback.py` handles unsupported input;
- `src/api/telegram/youtube.py` handles YouTube link messages and callback button clicks;
- `src/api/telegram/gpn.py` handles `/fuel`, fuel selection, and dismiss callbacks.

## Runtime Boot Process

Application startup is defined in `src/main.py`.

Boot sequence:

1. `AppConfig`, `BotConfig`, `YoutubeConfig`, and `GpnConfig` are loaded from environment variables.
2. Logging is configured through `configure_logging()`.
3. `ApplicationContext.from_configs(...)` creates concrete runtime objects.
4. `create_module_registry(context)` builds the active bot modules.
5. `create_dispatcher(...)` creates and configures `aiogram.Dispatcher`.
6. `Bot` is created with HTML parse mode enabled globally.
7. Webhook state is cleared via `bot.delete_webhook(drop_pending_updates=True)`.
8. Module startup hooks are executed.
9. Polling starts.
10. On shutdown, module shutdown hooks are executed and the bot session is closed.

## Dependency Wiring

The project currently uses a lightweight explicit dependency wiring pattern instead of a DI container.

### `ApplicationContext`

`src/logic/app/context.py` is the central runtime assembly point.

It currently contains:

- `app_config`
- `bot_config`
- `youtube_config`
- `youtube_store`
- `youtube_service`
- `gpn_config`
- `gpn_service`

This approach keeps object construction in one place and avoids hidden dependencies.

### Dispatcher Injection

`create_dispatcher(...)` stores shared services inside the dispatcher context:

```python
dispatcher["youtube_service"] = context.youtube_service
dispatcher["gpn_service"] = context.gpn_service
```

That allows `aiogram` to inject the service into handlers by parameter name.

Example:

```python
async def handle_youtube_message(message: Message, youtube_service: YoutubeService) -> None:
    ...
```

## Module System

The bot is designed around a module registry.

### Module Contract

`src/logic/modules/base.py` defines `BotModule` as a protocol with three members:

- `router() -> Router`
- `startup() -> None`
- `shutdown() -> None`

This is the minimal contract required for a pluggable bot feature.

### Module Registry

`src/logic/modules/registry.py` contains `ModuleRegistry`.

Responsibilities:

- expose all routers from registered modules;
- call `startup()` for every module during boot;
- call `shutdown()` for every module during shutdown.

### Module Registration

`src/logic/app/factory.py` is the current place where active modules are registered:

```python
def create_module_registry(context: ApplicationContext) -> ModuleRegistry:
    return ModuleRegistry(modules=(YoutubeModule(), GpnModule(...)), context=context)
```

This means adding a new module currently requires only one registry change after the module files are implemented.

## Telegram Update Flow

The dispatcher is wired in this order:

1. access middleware;
2. common router;
3. feature module routers;
4. fallback router.

That order matters.

### Access Control

`src/logic/bot/access.py` contains `AllowedUserMiddleware`.

Behavior:

- reads `event_from_user` from the `aiogram` event context;
- checks whether the Telegram user id is included in `BOT_ALLOWED_USER_IDS`;
- silently drops updates from non-allowed users.

This matches the requirement that unauthorized users should get no response at all.

### Common Router

`src/api/telegram/common.py` currently provides `/start`.

### Feature Routers

Feature routers contain their own message and callback flows.

### Fallback Router

`src/api/telegram/fallback.py` is intentionally included last.

If no module consumed the incoming message, fallback answers with a generic hint.

## YouTube Downloader Module

The YouTube feature is split across three layers.

### Core Layer

Files:

- `src/core/youtube/config.py`
- `src/core/youtube/models.py`
- `src/core/youtube/client.py`
- `src/core/youtube/utils.py`

Responsibilities:

- define config fields;
- define preview, option, request, progress, and result models;
- define the `YoutubeClient` protocol;
- provide formatting and URL extraction helpers.

### Logic Layer

Files:

- `src/logic/youtube/module.py`
- `src/logic/youtube/service.py`
- `src/logic/youtube/client.py`
- `src/logic/youtube/store.py`

Responsibilities:

- create the router-facing module object;
- manage request lifecycle and download orchestration;
- adapt `yt-dlp` to the internal `YoutubeClient` protocol;
- keep temporary request state in memory.

### API Layer

Files:

- `src/api/telegram/youtube.py`
- `src/api/telegram/filters.py`
- `src/api/telegram/callbacks.py`

Responsibilities:

- detect YouTube links in text messages;
- send preview messages with inline buttons;
- handle callback button clicks;
- launch background downloads without blocking the bot.

## YouTube Download Flow

Current end-to-end flow:

1. User sends a text message with a YouTube link.
2. `YoutubeUrlFilter` extracts and validates the URL.
3. `handle_youtube_message(...)` calls `YoutubeService.create_request_from_message(...)`.
4. `YoutubeService` calls `YoutubeClient.inspect(...)`.
5. `YtDlpYoutubeClient.inspect(...)` loads metadata and available formats with `yt-dlp`.
6. Bot sends a preview message with title, author, duration, and quality buttons.
7. Request metadata is stored in `YoutubeRequestStore` with a generated request id.
8. User presses an inline quality button.
9. `handle_quality_selection(...)` deletes the preview message and sends a progress message.
10. A background `asyncio` task starts `YoutubeService.process_download(...)`.
11. `YoutubeService` resolves the selected option and calls `YoutubeClient.download(...)`.
12. `YtDlpYoutubeClient.download(...)` downloads the media into `.runtime/youtube/<request_id>/...`.
13. `yt-dlp` progress hooks are translated into `YoutubeDownloadProgressSnapshot` updates.
14. `YoutubeService` throttles progress message edits with `progress_update_interval_seconds`.
15. When the file is ready, the bot sends the final video via `bot.send_video(...)`.
16. Progress message is deleted.
17. Original source message is deleted if `BOT_DELETE_SOURCE_MESSAGE=true`.
18. Temporary downloaded files are removed.

## Request Store Design

`src/logic/youtube/store.py` contains an in-memory TTL store.

Current characteristics:

- stores `YoutubeDownloadRequest` objects in a dictionary;
- generates request ids using `uuid4().hex[:12]`;
- removes expired requests lazily on `save()`, `get()`, and `pop()`;
- state is process-local and ephemeral.

Important implication:

- pending requests are lost on process restart;
- current design is acceptable for a personal bot, but not durable enough for multi-instance deployment.

## GPN Module

The GPN feature follows the same three-layer split as the YouTube module.

### Core Layer

Files:

- `src/core/gpn/config.py`
- `src/core/gpn/models.py`
- `src/core/gpn/client.py`
- `src/core/gpn/consts.py`

Responsibilities:

- define environment-based configuration;
- define station and fuel availability models;
- define the `GpnClient` protocol;
- keep request constants independent from runtime wiring.

### Logic Layer

Files:

- `src/logic/gpn/module.py`
- `src/logic/gpn/service.py`
- `src/logic/gpn/client.py`
- `src/logic/gpn/store.py`

Responsibilities:

- run the non-blocking polling lifecycle;
- call the GPN API through a persistent `httpx.AsyncClient` session;
- retain rotated session and CSRF cookies between requests;
- compare station `oils` values and detect only `false -> true` transitions;
- atomically persist and restore the latest station snapshot.

`GpnModule` is intentionally small: it starts and stops polling and sends notifications. State management and business rules belong to `GpnService`.

### API Layer

`src/api/telegram/gpn.py` contains the transport-specific behavior:

- handle `/fuel` and remove the source command;
- display fuel selection buttons grouped by octane number;
- replace the selection message with matching stations;
- build 2GIS links from station coordinates;
- handle the dismiss button.

### Polling And Persistence

On startup, `GpnService` restores `.runtime/gpn/state.json`. The first API response is compared with the restored snapshot, so availability changes that occurred while the container was stopped can still produce notifications.

After every successful API response, the new snapshot is written atomically. Docker Compose mounts the named `bot-runtime` volume at `/opt/app/.runtime`, so the state survives container restarts and recreation. Explicitly deleting volumes, for example with `docker compose down -v`, also deletes the persisted state.

## Configuration Model

Environment variables are loaded through `pydantic-settings`.

### `AppConfig`

Defined in `src/core/app/config.py`.

Variables:

- `APP_ENV`
- `APP_LOG_LEVEL`

### `BotConfig`

Defined in `src/core/bot/config.py`.

Variables:

- `BOT_TOKEN`
- `BOT_ALLOWED_USER_IDS`
- `BOT_DELETE_SOURCE_MESSAGE`
- `BOT_TELEGRAM_PROXY_URL`

Compatibility note:

- `ALLOWED_USER_IDS` is also accepted as a legacy alias.

### `YoutubeConfig`

Defined in `src/core/youtube/config.py`.

Variables:

- `YOUTUBE_DOWNLOAD_DIR`
- `YOUTUBE_COOKIES_PATH`
- `YOUTUBE_MAX_QUALITY`
- `YOUTUBE_PROGRESS_UPDATE_INTERVAL_SECONDS`
- `YOUTUBE_REQUEST_TTL_SECONDS`

### `GpnConfig`

Defined in `src/core/gpn/config.py`.

Variables:

- `GPN_URL`
- `GPN_CITY`
- `GPN_INTERVAL_SECONDS`
- `GPN_REQUEST_TIMEOUT_SECONDS`
- `GPN_RECIPIENT_IDS`
- `GPN_STATE_PATH`

## Quality Gates

The project uses four main quality checks:

- lint: `uv run ruff check src tests pyproject.toml`
- format check: `uv run ruff format --check src tests pyproject.toml`
- types: `uv run ty check`
- tests: `uv run pytest`

There is also a single convenience target:

```bash
make quality
```

## Local Commands

Main `Makefile` targets:

- `make quality`
- `make dev-up`
- `make dev-down`
- `make prod-up`
- `make prod-down`

## Docker Runtime

### Base Image

`Dockerfile` uses:

- `astral/uv:python3.14-bookworm`

It installs `ffmpeg`, then installs Python dependencies with `uv sync --frozen --no-dev`.

### Dev Compose

`docker-compose.dev.yml` is designed for local development.

Characteristics:

- mounts the whole project into the container;
- keeps a dedicated container `.venv` volume;
- runs `uv run python -m src.main`;
- sets `APP_ENV=dev`.

### Prod Compose

`docker-compose.prod.yml` is designed for production-like runtime.

Characteristics:

- no source bind mount;
- restart policy enabled;
- runs frozen environment command;
- sets `APP_ENV=prod`.

## How To Add a New Module

This is the main extension scenario the architecture is built for.

Below is the recommended pattern.

### 1. Create a `core` package for the feature

Example for a hypothetical notes feature:

```text
src/core/notes/
├── __init__.py
├── config.py
├── models.py
├── client.py
└── utils.py
```

Put here:

- pydantic models;
- feature config;
- protocols/interfaces;
- pure helpers.

Do not put `aiogram` routers or concrete runtime wiring here.

### 2. Create a `logic` package for the feature

Example:

```text
src/logic/notes/
├── __init__.py
├── module.py
├── service.py
├── client.py
└── store.py
```

Put here:

- concrete implementations;
- orchestration services;
- stores and runtime state;
- module lifecycle hooks.

Recommended pattern:

- `service.py` contains the main application flow;
- `client.py` contains the external adapter implementation;
- `module.py` exposes a `Router` and startup/shutdown hooks.

### 3. Create Telegram API handlers for the feature

Example:

```text
src/api/telegram/notes.py
src/api/telegram/filters.py
src/api/telegram/callbacks.py
```

Keep handlers thin.

Handlers should:

- parse Telegram input;
- call the feature service;
- return Telegram output.

Handlers should not contain complex business logic.

### 4. Extend `ApplicationContext`

If the new module needs config, stores, clients, or services, instantiate them in:

- `src/logic/app/context.py`

Example direction:

```python
notes_store = NotesStore(...)
notes_client = NotesApiClient(...)
notes_service = NotesService(...)
```

Then add them as fields in `ApplicationContext`.

### 5. Inject required services into the dispatcher

In `src/logic/app/factory.py`, expose the service through dispatcher context:

```python
dispatcher["notes_service"] = context.notes_service
```

This lets `aiogram` pass the service into handlers automatically.

### 6. Register the module in the registry

Still in `src/logic/app/factory.py`, add the module to `create_module_registry(...)`:

```python
return ModuleRegistry(modules=(YoutubeModule(), NotesModule()), context=context)
```

This is the only place where the new module becomes globally active.

### 7. Add tests

Recommended minimum:

- unit tests for pure utils and models;
- unit tests for service flow;
- unit tests for store behavior.

If the feature is complex or stateful, also add integration tests.

### 8. Update `.env.example` if the module introduces config

Any new environment variable must be documented there.

## Recommended Rules For New Modules

- Prefer protocols in `core` and concrete adapters in `logic`.
- Keep Telegram-specific code in `api`, not in `core`.
- Keep transport-independent orchestration in services.
- Keep startup wiring centralized in `ApplicationContext` and `factory.py`.
- Prefer async APIs and `asyncio.to_thread(...)` for blocking external libraries.
- Clean up temporary resources in `finally` blocks.
- Do not bypass `AllowedUserMiddleware` for privileged features.
- Preserve the router ordering so fallback stays last.

## Current Limitations

These are useful to know before extending the bot further.

- `YoutubeRequestStore` is in-memory only.
- There is no persistent queue or job runner.
- A long-running download is attached to the current process lifetime.
- Failed downloads are reported to the user, but there is no retry policy yet.
- The module registry is still manual, not auto-discovered.
- There are no integration or e2e Telegram tests yet.

## Good Next Improvements

Logical next steps for the project:

- add a persistent store for active requests and feature state;
- add structured application logging around module actions;
- add centralized error message builders for a consistent UX;
- add a reusable base pattern for module config and registration;
- add integration tests for handler-to-service flows;
- add rate limiting or concurrency caps for heavy download tasks;
- add metrics or observability hooks if the bot grows.

## Summary

The project is intentionally built around a simple modular pattern:

- `core` defines contracts and models;
- `logic` assembles and executes behavior;
- `api` exposes Telegram transport handlers;
- `ApplicationContext` wires dependencies;
- `ModuleRegistry` enables pluggable features;
- middleware protects access globally;
- background tasks keep the bot responsive during heavy operations.

For a personal Telegram bot, this architecture is small enough to stay maintainable and strict enough to scale with additional feature modules.
