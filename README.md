# The Perepilitsa Assistant

Персональный асинхронный Telegram-бот на Python и `aiogram`. Бот скачивает видео с YouTube и отслеживает наличие топлива на АЗС сети «Газпромнефть».

## Возможности

### YouTube Downloader

- Распознаёт ссылки `youtube.com` и `youtu.be`.
- Показывает доступные варианты качества и размер файла.
- Скачивает выбранное видео в фоне, не блокируя остальные команды.
- Показывает прогресс скачивания и загрузки в Telegram.
- Поддерживает cookies для видео, требующих авторизации.

### Мониторинг Топлива GPN

- Раз в заданный интервал получает список АЗС выбранного города.
- Отправляет уведомление, если топливо сменило состояние с «нет в наличии» на «в наличии».
- Объединяет изменения нескольких АЗС в одно сообщение.
- Сохраняет последнее состояние и восстанавливает его после перезапуска контейнера.
- По команде `/fuel` показывает виды топлива и АЗС, где они доступны.
- Добавляет к адресу ссылку на точку АЗС в 2GIS.

## Команды Бота

- `/start` — краткая справка.
- `/fuel` — выбор топлива и просмотр АЗС, где оно есть.
- Ссылка на YouTube — запуск сценария скачивания видео.

Бот отвечает только пользователям из `BOT_ALLOWED_USER_IDS`.

## Требования

Для рекомендуемого запуска нужны:

- Docker;
- Docker Compose v2;
- Telegram Bot Token от [@BotFather](https://t.me/BotFather).

Для запуска без Docker дополнительно нужны:

- Python 3.14;
- [uv](https://docs.astral.sh/uv/);
- `ffmpeg`;
- Deno 2.3+ и EJS-компоненты `yt-dlp` для решения JavaScript challenge YouTube.

## Быстрый Старт Через Docker

1. Клонируйте репозиторий:

```bash
git clone <URL_РЕПОЗИТОРИЯ>
cd the-perepilitsa-assistant
```

2. Создайте локальную конфигурацию:

```bash
cp .env.example .env
```

3. Заполните как минимум:

```env
BOT_TOKEN="<ТОКЕН_ОТ_BOTFATHER>"
BOT_ALLOWED_USER_IDS="123456789"
GPN_RECIPIENT_IDS="123456789"
GPN_CITY="Тюмень"
```

Узнать Telegram user ID можно с помощью специализированного Telegram-бота, например `@userinfobot`.

4. Запустите production-конфигурацию:

```bash
make prod-up
```

5. Посмотрите логи:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f bot
```

6. Остановите проект:

```bash
make prod-down
```

## Режимы Telegram API

По умолчанию бот использует облачный Telegram Bot API:

```env
BOT_TELEGRAM_API_BASE_URL=""
```

Для локального Telegram Bot API укажите:

```env
BOT_TELEGRAM_API_BASE_URL="http://telegram-bot-api:8081"
TELEGRAM_API_ID="<API_ID>"
TELEGRAM_API_HASH="<API_HASH>"
TELEGRAM_LOCAL="1"
```

И запускайте профиль `local-bot-api`:

```bash
make prod-up-local
```

Локальный API полезен для отправки больших файлов. `TELEGRAM_API_ID` и `TELEGRAM_API_HASH` выдаются на [my.telegram.org](https://my.telegram.org/).

## Конфигурация

Все настройки обязательны и читаются из `.env`. У config-классов нет скрытых значений по умолчанию. Неиспользуемые nullable-параметры задаются пустой строкой.

### Приложение

| Переменная | Описание | Пример |
| --- | --- | --- |
| `APP_ENV` | Режим окружения | `dev` |
| `APP_LOG_LEVEL` | Уровень логирования | `INFO` |
| `APP_RUNTIME_DIR` | Каталог runtime-данных | `.runtime` |

### Telegram-Бот

| Переменная | Описание | Пример |
| --- | --- | --- |
| `BOT_TOKEN` | Токен бота | `<CHANGE ME>` |
| `BOT_ALLOWED_USER_IDS` | Разрешённые user ID через запятую | `123,456` |
| `BOT_DELETE_SOURCE_MESSAGE` | Удалять исходную YouTube-ссылку после обработки | `true` |
| `BOT_TELEGRAM_API_BASE_URL` | URL локального Bot API или пустая строка | `""` |
| `BOT_TELEGRAM_PROXY_URL` | URL SOCKS/HTTP proxy или пустая строка | `""` |

### YouTube

| Переменная | Описание | Пример |
| --- | --- | --- |
| `YOUTUBE_DOWNLOAD_DIR` | Каталог временных загрузок | `.runtime/youtube` |
| `YOUTUBE_COOKIES_PATH` | Путь к Netscape cookies или пустая строка | `.secrets/youtube-cookies.txt` |
| `YOUTUBE_COOKIES_FROM_BROWSER` | Браузер для чтения cookies или пустая строка | `chrome` |
| `YOUTUBE_MAX_QUALITY` | Максимальная высота видео | `1080` |
| `YOUTUBE_PROGRESS_UPDATE_INTERVAL_SECONDS` | Частота обновления progress message | `1.5` |
| `YOUTUBE_TELEGRAM_UPLOAD_LIMIT_BYTES` | Лимит загружаемого файла | `2000000000` |
| `YOUTUBE_REQUEST_TTL_SECONDS` | Срок жизни выбора качества | `3600` |

Одновременно задавать `YOUTUBE_COOKIES_PATH` и `YOUTUBE_COOKIES_FROM_BROWSER` не рекомендуется. В Docker обычно используется файл cookies.

### GPN

| Переменная | Описание | Пример |
| --- | --- | --- |
| `GPN_URL` | Базовый URL API | `https://gpnbonus.ru` |
| `GPN_CITY` | Город для фильтрации АЗС | `Тюмень` |
| `GPN_INTERVAL_SECONDS` | Интервал опроса API | `60` |
| `GPN_REQUEST_TIMEOUT_SECONDS` | Таймаут HTTP-запроса | `30` |
| `GPN_RECIPIENT_IDS` | Получатели автоматических уведомлений | `123,456` |
| `GPN_STATE_PATH` | Файл постоянного snapshot | `.runtime/gpn/state.json` |

### Локальный Telegram Bot API

| Переменная | Описание |
| --- | --- |
| `TELEGRAM_HTTP_PORT` | HTTP-порт локального API |
| `TELEGRAM_API_ID` | Telegram API ID |
| `TELEGRAM_API_HASH` | Telegram API Hash |
| `TELEGRAM_LOCAL` | Включение local mode |

## YouTube Cookies

Для age-restricted, private или требующих авторизации видео можно передать cookies в Netscape-формате:

```env
YOUTUBE_COOKIES_PATH="/opt/app/.secrets/youtube-cookies.txt"
YOUTUBE_COOKIES_FROM_BROWSER=""
```

При Docker-запуске файл должен быть доступен внутри контейнера. Не добавляйте cookies и `.env` в Git.

Production Compose подключает локальный каталог `.secrets` к `/opt/app/.secrets` в режиме `read-only`. Перед запуском создайте каталог и поместите в него файл:

```bash
mkdir -p .secrets
cp <ПУТЬ_К_COOKIES> .secrets/youtube-cookies.txt
```

В `.env` укажите контейнерный путь:

```env
YOUTUBE_COOKIES_PATH="/opt/app/.secrets/youtube-cookies.txt"
```

## Локальная Разработка

1. Установите `uv` и Python 3.14.
2. Установите зависимости:

```bash
uv sync --group dev
```

3. Создайте `.env`:

```bash
cp .env.example .env
```

4. Запустите бота напрямую:

```bash
uv run python -m src.main
```

Для разработки в Docker с автоматическим перезапуском:

```bash
make dev-up
```

С локальным Telegram Bot API:

```bash
make dev-up-local
```

## Проверка Качества

Полный набор проверок:

```bash
make quality
```

Отдельные команды:

```bash
make lint
make format
make types
make test
```

Эквивалентные команды `uv`:

```bash
uv run ruff check src tests pyproject.toml
uv run ruff format --check src tests pyproject.toml
uv run ty check
uv run pytest
```

## Хранение Данных

- Временные YouTube-файлы находятся в `.runtime/youtube` и удаляются после обработки.
- GPN snapshot находится в `.runtime/gpn/state.json`.
- Docker Compose монтирует `.runtime` в named volume `bot-runtime`.
- State сохраняется при restart и пересоздании контейнера.
- Команда `docker compose down -v` удаляет named volumes и сохранённый state.

## Обновление

```bash
git pull
make prod-up
```

`make prod-up` пересобирает image и перезапускает сервис.

## Диагностика

Проверить состояние контейнеров:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

Посмотреть логи:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f bot
```

Проверить итоговую Compose-конфигурацию:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
```

Частые проблемы:

- Бот не отвечает: проверьте `BOT_TOKEN` и наличие user ID в `BOT_ALLOWED_USER_IDS`.
- `/fuel` не показывает данные: проверьте `GPN_URL`, `GPN_CITY` и логи GPN poller.
- YouTube-видео требует входа: настройте `YOUTUBE_COOKIES_PATH`.
- Бот не подключается к локальному Bot API: запускайте `make dev-up-local` или `make prod-up-local`.
- State исчез после остановки: не используйте `docker compose down -v`, если volume нужно сохранить.

## Структура Проекта

```text
src/
├── api/telegram/       # Telegram handlers, callbacks и клавиатуры
├── core/               # Конфигурация, модели и protocol-контракты
├── logic/              # Сервисы, adapters, stores и lifecycle модулей
└── main.py              # Точка запуска
tests/unit/              # Unit-тесты
```

Правила для разработчиков и AI-агентов находятся в [AGENTS.md](AGENTS.md).

## Безопасность

- Не публикуйте `.env`, Telegram token, cookies и API credentials.
- Ограничивайте доступ через `BOT_ALLOWED_USER_IDS`.
- Используйте отдельного Telegram-бота для development и production, если проект разворачивается в нескольких окружениях.

## Лицензия

Отдельный файл лицензии в репозитории пока отсутствует. До добавления лицензии использование и распространение кода регулируется владельцем проекта.
