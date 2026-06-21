# CLAUDE.md — Mail Print Agent

> Контекст и правила проекта для Claude Code. Читать перед любой задачей.
> Язык общения с пользователем — русский. Идентификаторы кода, имена переменных
> окружения и команды — на английском.

## 1. Что это за приложение

Демон, который периодически опрашивает почтовый ящик по IMAP, забирает из новых
писем вложения, при необходимости конвертирует их в PDF и отправляет на сетевой
принтер. После успешной печати вложение сохраняется в локальную (примонтированную
на хост) директорию, а письмо удаляется из ящика.

Параметры печати задаются:
1. дефолтами в `.env`;
2. опционально — кодом в начале текста письма (3 символа, см. §5).

Работает в Docker-контейнере, запускается через `compose.yaml`, целевая ОС хоста —
Ubuntu / Linux Mint.

## 2. Стек и инструменты

- **Python 3.12**
- Управление зависимостями — **uv** (`pyproject.toml`).
- IMAP — **imap-tools**.
- Конфиг — **pydantic-settings** (валидация `.env` на старте).
- Состояние/журнал — **SQLite** (stdlib `sqlite3`), файл на volume.
- Печать — **CUPS внутри контейнера** + клиент `lp` через `subprocess` (ADR-002).
- Конвертация office-форматов в PDF — **LibreOffice headless** (ADR-005).
- Lint/format — **ruff**. Тесты — **pytest**.
- Логи — `logging` в stdout, уровень из `LOG_LEVEL`.

Код пишем профессионально: **SOLID, DRY, KISS**. Архитектурные требования — §11.

## 3. Структура проекта

```
mail-print-agent/
├── compose.yaml
├── Dockerfile
├── entrypoint.sh          # настройка CUPS-принтера + cupsd + app
├── .env.example
├── allowed_senders.txt.example
├── .gitignore             # .env, allowed_senders.txt, data/, printed/, __pycache__
├── pyproject.toml
├── CLAUDE.md
├── app/
│   ├── __init__.py
│   ├── main.py            # композиция зависимостей, цикл, graceful shutdown
│   ├── config.py          # Settings (pydantic-settings)
│   ├── models.py          # Message, Attachment, PrintOptions, PrintResult
│   ├── interfaces.py      # Protocol: MailSource, Printer, Converter, StateStore, Storage
│   ├── mailbox.py         # ImapMailSource
│   ├── parser.py          # тело письма -> PrintOptions
│   ├── converter.py       # LibreOfficeConverter (+ NullConverter для PDF/изображений)
│   ├── printer.py         # CupsPrinter
│   ├── storage.py         # LocalAttachmentStorage (сохранение в printed/)
│   ├── state.py           # SqliteStateStore (дедуп + журнал)
│   └── allowlist.py       # загрузка белого списка из env и/или файла
├── data/                  # SQLite, монтируется на хост (volume)
├── printed/               # сохранённые распечатанные файлы, на хост (volume)
├── docs/
│   ├── adr/
│   └── specs/
└── tests/
    ├── test_parser.py
    ├── test_allowlist.py
    └── test_printer.py
```

## 4. Конфигурация (.env)

```dotenv
# --- IMAP ---
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_SSL=true
IMAP_USER=user@example.com
IMAP_PASSWORD=app-specific-password
IMAP_FOLDER=INBOX
POLL_INTERVAL=60                 # секунды между опросами

# --- Безопасность ---
# Белый список: значения из ALLOWED_SENDERS объединяются с адресами из файла.
ALLOWED_SENDERS=me@example.com,boss@example.com
ALLOWED_SENDERS_FILE=/app/allowed_senders.txt    # опционально; пусто = не использовать
MAX_ATTACHMENT_MB=20
ALLOWED_EXTENSIONS=pdf,png,jpg,jpeg,docx,doc,xlsx,xls,odt,ods,txt

# --- Обработка вложений ---
PRINT_ATTACHMENTS=FIRST          # FIRST | ALL  (default FIRST)
PRINTED_DIR=/data/printed        # внутри контейнера; на хост через volume -> ./printed

# --- После печати ---
DELETE_FROM_MAILBOX=true         # удалять письмо из ящика после успешной печати

# --- Принтер (CUPS внутри контейнера) ---
PRINTER_NAME=office
PRINTER_URI=ipp://192.168.1.50/ipp/print   # или socket://192.168.1.50:9100
PRINT_DEFAULT_ORIENTATION=P      # P=portrait | L=landscape
PRINT_DEFAULT_SIDES=2            # 1=односторонняя | 2=двусторонняя
PRINT_DEFAULT_EDGE=l             # s=short edge | l=long edge

# --- Прочее ---
DB_PATH=/data/state.db
TZ=Europe/Moscow
LOG_LEVEL=INFO
```

`config.py` валидирует значения на старте (например, `ORIENTATION ∈ {P,L}`,
`PRINT_ATTACHMENTS ∈ {FIRST,ALL}`) и падает с понятной ошибкой, а не в рантайме.

## 5. Грамматика кода печати в теле письма

Берём первые **3 непробельных символа** plain-text части письма. Если они не
проходят валидацию — целиком используем дефолты из `.env` (не частично).

| Позиция | Значения | Смысл | CUPS-опция |
|---------|----------|-------|------------|
| 1 | `P` / `L` | ориентация | `orientation-requested=3` / `4` |
| 2 | `1` / `2` | односторонняя / двусторонняя | `sides=...` |
| 3 | `s` / `l` | край переплёта | используется только при `2` |

Маппинг `sides`: `1` → `one-sided`; `2`+`s` → `two-sided-short-edge`;
`2`+`l` → `two-sided-long-edge`. Регистр символов игнорируем (нормализуем).

> **Готча с ориентацией:** для PDF со своей ориентацией принудительный
> `orientation-requested` может повернуть содержимое. Тестировать на реальном PDF.

## 6. Алгоритм основного цикла (main.py)

1. Загрузить и провалидировать `Settings`; собрать зависимости (DI, см. §11).
2. Инициализировать SQLite (создать таблицу при отсутствии).
3. Загрузить белый список (env + файл).
4. В бесконечном цикле каждые `POLL_INTERVAL` секунд:
   - подключиться к IMAP, выбрать письма в `IMAP_FOLDER`;
   - для каждого письма:
     - проверить отправителя по белому списку — иначе пропустить и залогировать;
     - проверить дедуп по `Message-ID` — если обработано, пропустить;
     - распарсить тело -> `PrintOptions` (дефолты при ошибке);
     - отобрать вложения по `ALLOWED_EXTENSIONS` и `MAX_ATTACHMENT_MB`;
       при `PRINT_ATTACHMENTS=FIRST` — взять первое подходящее, при `ALL` — все;
     - для каждого: при необходимости конвертировать в PDF (LibreOffice),
       отправить в печать, сохранить исходный файл в `PRINTED_DIR`;
     - записать результат и список сохранённых имён файлов в БД;
     - при успешной печати **всех** отобранных вложений и `DELETE_FROM_MAILBOX=true`
       — удалить письмо из ящика;
   - закрыть соединение.
5. Корректно завершаться по `SIGTERM`/`SIGINT`.

Каждая итерация и каждое письмо обёрнуты в try/except — единичная ошибка не должна
ронять демон. Письмо удаляется только после подтверждённого успеха, иначе остаётся
для повторной попытки на следующей итерации.

## 7. SQLite: дедупликация + журнал

Ключ дедупликации — заголовок **`Message-ID`** (стабилен между сессиями, в отличие
от UID, сбрасываемого при смене `UIDVALIDITY`).

```sql
CREATE TABLE IF NOT EXISTS processed (
    message_id   TEXT PRIMARY KEY,
    sender       TEXT,
    subject      TEXT,
    status       TEXT,            -- printed | partial | rejected | error
    saved_files  TEXT,            -- JSON-массив имён сохранённых файлов
    error        TEXT,            -- текст ошибки при status=error
    processed_at TEXT
);
```

## 8. Печать и сохранение

**Конвертация:** PDF и изображения печатаются как есть; office-форматы
(`docx/doc/xlsx/xls/odt/ods`) предварительно конвертируются в PDF командой
`libreoffice --headless --convert-to pdf --outdir <tmp> <file>`. Выбор конвертера —
по расширению (Strategy, см. §11).

**Печать** через `subprocess`:

```
lp -d {PRINTER_NAME} \
   -o orientation-requested={3|4} \
   -o sides={one-sided|two-sided-long-edge|two-sided-short-edge} \
   {pdf_path}
```

Проверять код возврата `lp`; ошибку логировать и писать `status=error`.

**Сохранение:** исходное вложение копируется в `PRINTED_DIR` (на хосте — `./printed`).
Имя файла делать уникальным, чтобы не перезатирать (например,
`{YYYYMMDD-HHMMSS}_{message-id-hash}_{original_name}`). Сохранённые имена — в БД.
Временные файлы (скачанное вложение, промежуточный PDF) после обработки удалять.

## 9. Контейнеризация

- **Dockerfile**: `python:3.12-slim`; ставим `cups`, `cups-client`, фильтры печати,
  `libreoffice-core`/`libreoffice` (headless, без GUI — следить за размером образа);
  зависимости через uv; копируем `app/` и `entrypoint.sh`.
- **entrypoint.sh**: `lpadmin -p $PRINTER_NAME -E -v $PRINTER_URI -m everywhere`
  регистрирует принтер дефолтным, запускает `cupsd`, затем `exec` Python-приложение
  (чтобы сигналы доходили до процесса).
- **compose.yaml**: сервис `mail-print-agent`, `env_file: .env`,
  `restart: unless-stopped`, `init: true`, volumes:
  - `./data:/data` — SQLite (`DB_PATH=/data/state.db`);
  - `./printed:/data/printed` — сохранённые файлы;
  - `./allowed_senders.txt:/app/allowed_senders.txt:ro` — белый список (если используется).
  Принтер сетевой — проброс USB не нужен.

## 10. ADR (кратко, расписать в docs/adr/)

- **ADR-001. IMAP polling, не IDLE.** Простота и устойчивость к разрывам.
- **ADR-002. CUPS внутри контейнера.** Надёжное соблюдение `-o` опций (дуплекс,
  ориентация) на разных принтерах.
- **ADR-003. Дедуп по `Message-ID`.** Устойчив к смене `UIDVALIDITY`.
- **ADR-004. Белый список отправителей обязателен.** Печать по письму — публичный
  триггер. Источник — env и/или текстовый файл (объединяются).
- **ADR-005. LibreOffice headless для конвертации.** Покрывает office-форматы ценой
  размера образа; альтернативы (микросервис конвертации) избыточны для домашнего стенда.
- **ADR-006. Удаление письма только после успеха.** Гарантия «не потеряли, но и не
  напечатали дважды» обеспечивается дедупом + удалением после подтверждённой печати.

## 11. Архитектура: SOLID / DRY

Приложение строим на **инверсии зависимостей**. В `interfaces.py` объявляем
`Protocol` (или ABC) для внешних взаимодействий, реализации внедряем в `main.py`:

- `MailSource` — `fetch()`, `delete(message)`; реализация `ImapMailSource`.
- `Printer` — `print(pdf_path, options)`; реализация `CupsPrinter`.
- `Converter` — `to_pdf(path) -> path`; `LibreOfficeConverter`, `NullConverter`.
- `StateStore` — `is_processed()`, `record()`; `SqliteStateStore`.
- `AttachmentStorage` — `save(attachment) -> filename`; `LocalAttachmentStorage`.

Принципы:
- **SRP** — один модуль = одна ответственность (IMAP не знает о печати, печать не
  знает об IMAP; оркестрация — только в `main.py`).
- **OCP/DIP** — `main.py` зависит от протоколов, не от конкретики. Новый источник
  почты или принтер добавляется без правки оркестратора.
- **Strategy** для выбора конвертера по расширению; маппинг кода печати в CUPS —
  единая функция (DRY), переиспользуется и в тестах.
- Конфиг — только через `Settings`, переданный в конструкторы; **никаких** `os.getenv`
  и глобального состояния по коду.
- Чистые функции там, где возможно (парсер кода печати, allowlist) — легко тестируются.

## 12. Конвенции

- Type hints везде; публичные функции — с докстрингами.
- Перед коммитом: `ruff format && ruff check && pytest`.
- Никаких секретов и реальных адресов в коммитах; правим `*.example`.
- Юнит-тестами покрыть: парсер кода печати (вкл. невалидный ввод), маппинг CUPS,
  загрузку белого списка (env + файл + объединение).
- Тесты не требуют реального принтера/почты: `lp`, IMAP и LibreOffice мокать.

## 13. Команды

```bash
# Локальная разработка
uv sync
uv run python -m app.main

# Тесты и линт
uv run pytest
uv run ruff check && uv run ruff format

# Контейнер
docker compose up -d --build
docker compose logs -f
docker compose down
```

## 14. Зафиксированные решения

1. 2-й символ кода: `1` — односторонняя, `2` — дуплекс.
2. `PRINT_ATTACHMENTS=FIRST|ALL`, дефолт `FIRST`.
3. Office-форматы конвертируются через LibreOffice.
4. После печати: сохранить файл в `./printed` (volume) и удалить письмо из ящика.
