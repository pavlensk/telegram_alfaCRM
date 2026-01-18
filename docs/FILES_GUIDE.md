# 📋 Путеводитель по файлам проекта

## 🚀 Точка входа

### **main.py** (108 строк)
```python
# Что делает:
✅ Инициализирует ресурсы (JSON)
✅ Создаёт Bot и Dispatcher
✅ Регистрирует все хендлеры
✅ Запускает бот и веб-сервер параллельно
✅ Обрабатывает graceful shutdown

# Как использовать:
python main.py

# Ключевые функции:
- async def main() → Главная функция
- async def run_bot(bot) → Запуск диспетчера

# Импортирует из:
config, resources_loader, web_server, bot_notifications,
crm_client, quiz_manager, handlers
```

---

## ⚙️ Конфигурация

### **config.py** (70 строк)
```python
# Что делает:
✅ Загружает переменные окружения из .env
✅ Определяет enum Section (SWIMMING, RUNNING, TRIATHLON)
✅ Объявляет глобальные переменные

# Переменные окружения:
BOT_TOKEN → Токен Telegram бота
ALFA_EMAIL → Email для AlfaCRM
ALFA_API_KEY → API ключ AlfaCRM
COORDINATOR_USERNAME → @username координатора
ALFA_BASE → Base URL AlfaCRM
SWIMMING_BASE_URL → Базовая ссылка на программы
PORT → Порт веб-сервера (default: 8000)
BOT_STATUS_CHAT_ID → Chat ID для уведомлений (опционально)

# Глобальные переменные (заполняются в resources_loader):
UI_LABELS → Dict с текстами кнопок
SECTIONS → Dict с секциями
QUIZ_DATA → Dict с вопросами квиза
TEXTS → Dict с текстовыми сообщениями
LEVEL_RESULTS → Dict результатов уровней
LEVEL_PATHS → Dict путей к программам
SECTION_TITLES → Dict заголовков секций
HELLO_BY_SECTION → Dict приветствий

# Используется:
Всеми модулями для доступа к конфигурации

# Пример:
import config
print(config.BOT_TOKEN)
title = config.SECTION_TITLES.get(config.Section.SWIMMING)
```

---

## 📦 Загрузчик ресурсов

### **resources_loader.py** (80 строк)
```python
# Что делает:
✅ Определяет класс Resources для загрузки JSON
✅ Функция initialize_resources() заполняет конфиг

# Ключевой класс:
class Resources:
    RESOURCES_DIR = Path(__file__).parent / "resources"
    
    @classmethod
    def load(filename: str) -> Dict:
        # Читает JSON файл с валидацией
        # Логирует "✅ Loaded resource: {filename}"
        # Выбросит FileNotFoundError или RuntimeError

# Ключевая функция:
def initialize_resources():
    # Читает UI_LABELS, SECTIONS, QUIZ_DATA, TEXTS
    # Парсит quiz_indices
    # Преобразует level_results в кортежи (min, max)
    # Заполняет SECTION_TITLES и HELLO_BY_SECTION
    # Логирует результат

# Когда вызывается:
В main.py перед запуском бота:
resources_loader.initialize_resources()

# Пример структуры JSON:
{
    "sections": {
        "swimming": {"title": "Плавание", "hello": "Привет пловец!"},
        ...
    }
}
```

---

## 🔧 Утилиты

### **utils.py** (49 строк)
```python
# Что делает:
✅ Преобразование и валидация данных
✅ Генерирование строк для UI
✅ Парсинг callback_data

# Функции:
def normalize_ru_phone_to_plus7(text: str) -> Optional[str]
    # Входит: "89999999999", "9999999999", "+79999999999"
    # Выход: "79999999999" или None
    # Используется: в handlers/customer.py

def coordinator_link(start_text: str) -> str
    # Входит: "Привет координатор!"
    # Выход: "https://t.me/username?text=Привет%20координатор!"
    # Используется: в keyboards.py, handlers/quiz.py

def parse_section(raw: str) -> Section
    # Входит: "swimming"
    # Выход: Section.SWIMMING
    # Используется: в handlers/navigation.py, handlers/customer.py

def title_root() -> str
    # Выход: "Выберите направление:"

def title_section(section: Section) -> str
    # Входит: Section.SWIMMING
    # Выход: "Плавание. Выберите действие:"

# Импортируется:
handlers/navigation.py, keyboards.py, handlers/customer.py
```

---

## ⌨️ Клавиатуры

### **keyboards.py** (107 строк)
```python
# Что делает:
✅ Генерирует InlineKeyboardMarkup для всех меню

# Функции:
def kb_root_inline(ui_labels: Dict) -> InlineKeyboardMarkup
    # Главное меню: Плавание, Бег, Триатлон
    # Используется: handlers/navigation.py::start()

def kb_section_inline(section: Section, ui_labels: Dict) -> InlineKeyboardMarkup
    # Меню конкретной секции:
    # - Написать координатору (URL)
    # - Уточнить баланс (act:lesson_remainder)
    # - Для SWIMMING: Уровень, Сертификация, Подготовка, Тренировка
    # - Назад (nav:root)
    # Используется: handlers/navigation.py, handlers/customer.py

def get_question_keyboard_adaptive(q_data, uid=None, quiz_state=None)
    # Клавиатура для вопросов квиза
    # Динамическая нумерация: А), Б), В)
    # Для вопроса 5 скрывает вариант "a" если score > 2
    # Используется: handlers/quiz.py

# Зависит от:
config.UI_LABELS (тексты кнопок)
config.HELLO_BY_SECTION (приветствия)
utils.coordinator_link()

# Импортируется:
handlers/navigation.py, handlers/customer.py, handlers/quiz.py
```

---

## 🔌 Клиент AlfaCRM

### **crm_client.py** (117 строк)
```python
# Что делает:
✅ Асинхронный HTTP клиент для AlfaCRM API
✅ Управление токенами (логин, кэш, переполучение)
✅ Поиск клиентов по номеру телефона

# Ключевой класс:
class AlfaCRMClient:
    def __init__(email: str, apikey: str)
        # Инициализирует клиент
    
    async def login(client: httpx.AsyncClient) -> str
        # POST на /v2api/auth/login
        # Возвращает токен
        # Выбросит RuntimeError если статус != 200
    
    async def get_token(client: httpx.AsyncClient) -> str
        # Возвращает кэшированный токен если не истёк (12ч)
        # Иначе получает новый через login()
        # Использует asyncio.Lock для thread-safety
    
    async def customer_search_by_phone(phone_plus7: str) -> Dict
        # POST на /v2api/3/customer/index с номером
        # Если 401/403 - переполучает токен и повторяет
        # Возвращает JSON ответ или выбросит RuntimeError

# Функция:
def extract_customer_fields(resp: Dict) -> Optional[Dict]
    # Извлекает поля из ответа API:
    # - legal_name (ФИ клиента)
    # - balance (остаток средств)
    # - paid_lesson_count (кол-во оплаченных уроков)
    # Возвращает None если нет данных

# Используется:
handlers/customer.py при поиске клиента
main.py::run_bot() для создания alfa = AlfaCRMClient(...)

# Пример:
try:
    resp = await alfa.customer_search_by_phone("79999999999")
    customer = extract_customer_fields(resp)
    print(customer["legal_name"])
except Exception as e:
    print(f"Ошибка: {e}")
```

---

## 📝 Менеджер меню

### **menu_manager.py** (71 строка)
```python
# Что делает:
✅ Управление меню-сообщениями (отправка и редактирование)
✅ Гарантирует одно меню-сообщение на пользователя

# Функции:
async def ensure_menu_message(m, menu_msg_id_by_user, text, markup)
    # Если есть сохранённый message_id → редактирует его
    # Иначе → отправляет новое сообщение
    # Сохраняет новый ID в menu_msg_id_by_user[uid]
    # Используется: когда пришло Message от пользователя

async def edit_menu_message(cq, menu_msg_id_by_user, text, markup)
    # Если есть сохранённый message_id → редактирует его
    # Иначе пытается отредактировать текущее сообщение
    # Если не получится → отправляет новое
    # Сохраняет ID в menu_msg_id_by_user[uid]
    # Используется: при CallbackQuery (нажатие кнопки)

# Состояние:
menu_msg_id_by_user: Dict[int, int]
    # uid → message_id последнего меню
    # Передаётся в обе функции

# Используется:
Все handlers: navigation.py, customer.py
```

---

## 🎯 Менеджер квиза

### **quiz_manager.py** (116 строк)
```python
# Что делает:
✅ Управление состоянием квиза
✅ Валидация состояния с TTL
✅ Адаптивная логика переходов между вопросами
✅ Вычисление результатов

# Ключевой класс:
class QuizManager:
    def __init__()
        # quiz_state: Dict[uid] = {
        #     "question_idx": int,
        #     "score": int,
        #     "timestamp": float
        # }
    
    def validate_quiz_state(uid: int) -> bool
        # Проверяет: uid есть в state и не истёк TTL
        # Если истёк → удаляет из state
        # Возвращает bool
    
    def init_quiz(uid: int)
        # Создаёт новый квиз для uid
        # Начинает с QUIZ_IDX_FORMAT, score=0, текущее время
    
    def adaptive_next_question(uid, current_q_idx, current_answer) -> int
        # Вычисляет баллы за ответ и добавляет к score
        # Применяет адаптивную логику:
        #   - Если формат = "б" (персональные) → конец
        #   - Если опыт = "a" или "c" → пропустить расстояние
        #   - Если расстояние = "a" → пропустить кроль
        # Возвращает индекс следующего вопроса или len(questions)
    
    def get_quiz_result(uid: int) -> Dict
        # Возвращает результат: {
        #     "title": "🌊 Level 3",
        #     "desc": "Описание",
        #     "path": "path/to/program",
        #     "score": 6
        # }
    
    def finish_quiz(uid: int)
        # Удаляет uid из quiz_state

# Состояние:
quiz_state хранится в QuizManager экземпляре
Передаётся в handlers/quiz.py

# Используется:
handlers/quiz.py для всей логики квиза
main.py::run_bot() для создания quiz_mgr = QuizManager()

# Пример:
quiz_mgr = QuizManager()
quiz_mgr.init_quiz(uid=123)
next_idx = quiz_mgr.adaptive_next_question(123, 0, "a")
result = quiz_mgr.get_quiz_result(123)
quiz_mgr.finish_quiz(123)
```

---

## 🌐 Веб-сервер

### **web_server.py** (34 строки)
```python
# Что делает:
✅ Запускает HTTP сервер на aiohttp
✅ Обслуживает health check запросы

# Функции:
async def handle_root(request: Request) -> Response
    # GET / → "Sports Bot OK\n"

async def start_web_app()
    # Создаёт Application
    # Добавляет route GET /
    # Слушает на 0.0.0.0:PORT
    # Логирует "✅ Web server listening on port {PORT}"
    # Бесконечный loop с sleep(3600)

# Используется:
main.py::main() запускает как задача:
web_task = asyncio.create_task(start_web_app())

# Зависит от:
config.PORT
```

---

## 📢 Уведомления

### **bot_notifications.py** (48 строк)
```python
# Что делает:
✅ Отправляет уведомления о запуске/остановке бота

# Функции:
async def notify_bot_ready(bot: Bot)
    # Если BOT_STATUS_CHAT_ID задан:
    # Отправляет сообщение вида:
    # "🤖 Sports Bot запущен!
    #  🕐 2025-01-19 12:30:00
    #  ✅ AlfaCRM: OK
    #  ✅ Web: порт 8000"
    # Логирует результат

async def notify_bot_stopped(bot: Bot)
    # Отправляет "🛑 Sports Bot остановлен"

# Используется:
main.py::run_bot() - вызывает перед polling
main.py::main() - вызывает при shutdown

# Зависит от:
config.BOT_STATUS_CHAT_ID
config.PORT
```

---

## 📂 Хендлеры (handlers/)

### **handlers/__init__.py**
```python
# Экспорирует функции регистрации хендлеров:
from .navigation import setup_navigation_handlers
from .customer import setup_customer_handlers
from .quiz import setup_quiz_handlers
from .sections import setup_sections_handlers

# Используется:
main.py::run_bot() вызывает:
handlers.setup_navigation_handlers(dp, ...)
handlers.setup_customer_handlers(dp, ...)
handlers.setup_quiz_handlers(dp, ...)
handlers.setup_sections_handlers(dp)
```

### **handlers/navigation.py** (60 строк)
```python
# Что делает:
✅ Регистрирует хендлеры навигации по меню

# Функция:
def setup_navigation_handlers(dp, menu_msg_id_by_user, waiting_phone_section_by_user)

# Хендлеры:
@dp.message(F.command("start"))
async def start(m: Message)
    # /start → показывает главное меню

@dp.callback_query(F.data == "nav:root")
async def nav_root(cq: CallbackQuery)
    # Кнопка "Назад" → возврат в главное меню

@dp.callback_query(F.data.startswith("nav:section:"))
async def nav_section(cq: CallbackQuery)
    # nav:section:swimming → показывает меню плавания
    # nav:section:running → показывает меню бега
    # nav:section:triathlon → показывает меню триатлона

# Используется:
main.py::run_bot() для регистрации
```

### **handlers/customer.py** (122 строки)
```python
# Что делает:
✅ Регистрирует хендлеры для поиска клиентов

# Функция:
def setup_customer_handlers(dp, menu_msg_id_by_user, waiting_phone_section_by_user, alfa)

# Хендлеры:
@dp.callback_query(F.data.startswith("act:lesson_remainder:"))
async def act_lesson_remainder(cq: CallbackQuery)
    # Кнопка "Уточнить баланс" → просит номер телефона
    # Сохраняет секцию в waiting_phone_section_by_user[uid]

@dp.message(F.text)
async def handle_text(m: Message)
    # Если waiting_phone_section_by_user[uid] не None:
    #   - Нормализует номер через utils.normalize_ru_phone_to_plus7()
    #   - Если валидный: ищет через alfa.customer_search_by_phone()
    #   - Показывает результат (ФИ, баланс, уроки)
    # Иначе: показывает главное меню

# Используется:
main.py::run_bot() для регистрации
```

### **handlers/quiz.py** (128 строк)
```python
# Что делает:
✅ Регистрирует хендлеры для квиза

# Функция:
def setup_quiz_handlers(dp, quiz_mgr)

# Хендлеры:
@dp.callback_query(F.data == "sw:level")
async def sw_level_start(cq: CallbackQuery)
    # Кнопка "Определить уровень" → начинает квиз
    # Инициализирует quiz_mgr.init_quiz(uid)
    # Показывает первый вопрос

@dp.callback_query(F.data.startswith("quiz:answer:"))
async def quiz_answer(cq: CallbackQuery)
    # Ответ на вопрос → вычисляет следующий вопрос
    # Если квиз завершён → показывает результат
    # Иначе → показывает следующий вопрос

async def show_quiz_result(cq, uid, quiz_mgr)
    # Вспомогательная функция
    # Получает результат через quiz_mgr.get_quiz_result()
    # Показывает уровень и две кнопки:
    # - "Подробнее о программе" (URL)
    # - "Написать координатору" (mailto-like)

# Используется:
main.py::run_bot() для регистрации
```

### **handlers/sections.py** (38 строк)
```python
# Что делает:
✅ Регистрирует хендлеры для информационных разделов

# Функция:
def setup_sections_handlers(dp)

# Хендлеры:
@dp.callback_query(F.data == "sw:cert")
async def sw_cert(cq: CallbackQuery)
    # Кнопка "Сертификация" → показывает информацию

@dp.callback_query(F.data == "sw:prep")
async def sw_prep(cq: CallbackQuery)
    # Кнопка "Подготовка" → показывает информацию

@dp.callback_query(F.data == "sw:take")
async def sw_take(cq: CallbackQuery)
    # Кнопка "Тренировки" → показывает информацию

# Используется:
main.py::run_bot() для регистрации
```

---

## 📄 Ресурсы (resources/)

```
resources/
├── ui_labels.json         # Тексты кнопок
├── sections.json          # Названия секций
├── quiz_questions.json    # Вопросы квиза
└── texts.json            # Текстовые сообщения
```

### **ui_labels.json**
```json
{
    "btn_swimming": "🏊 Плавание",
    "btn_running": "🏃 Бег",
    ...
}
```

### **sections.json**
```json
{
    "sections": {
        "swimming": {
            "title": "Плавание",
            "hello": "Привет пловец!"
        },
        ...
    }
}
```

### **quiz_questions.json**
```json
{
    "questions": [...],
    "quiz_ttl_seconds": 600,
    "quiz_indices": {"format": 0, "experience": 1, ...},
    "level_results": {
        "(0,2)": {"title": "Level 1", "desc": "...", "path": "..."},
        ...
    }
}
```

### **texts.json**
```json
{
    "invalid_phone": "Неверный номер",
    "client_not_found": "Клиент не найден",
    ...
}
```

---

## 📋 Файлы конфигурации

### **.env** (не в git)
```
TELEGRAM_BOT_TOKEN=123456:ABC...
ALFA_EMAIL=user@example.com
...
```

### **.env.example** (в git)
```
# Пример конфигурации для разработчиков
```

### **.gitignore**
```
.env
__pycache__/
*.pyc
...
```

---

## 📚 Документация

### **README.md**
- Обзор проекта
- Установка и запуск
- Структура проекта
- Функциональность

### **MIGRATION.md**
- Как код разбит из монолита
- Маппинг функций
- Как работает интеграция

### **ARCHITECTURE.md**
- Диаграммы архитектуры
- Data flow сценарии
- Принципы дизайна
- Структура состояний

### **FILES_GUIDE.md** (этот файл)
- Подробное описание каждого модуля
- Что делает каждый файл
- Как они связаны

---

## 🔗 Связи между модулями

```
main.py
├─> config (читает)
├─> resources_loader (инициализирует)
├─> crm_client (создаёт объект alfa)
├─> quiz_manager (создаёт объект quiz_mgr)
├─> web_server (запускает)
├─> bot_notifications (отправляет уведомления)
└─> handlers (регистрирует все)
    ├─> navigation (меню)
    ├─> customer (поиск клиентов)
    ├─> quiz (квиз)
    └─> sections (информация)

config
├─> Используется: всеми модулями
└─> Заполняется: resources_loader

resources_loader
├─> Читает: resources/*.json
└─> Заполняет: config.*

utils
├─> Используется: keyboards, handlers, quiz_manager
└─> Использует: config

keyboards
├─> Используется: handlers
└─> Использует: config, utils

crm_client
├─> Используется: handlers/customer
└─> Использует: config

menu_manager
├─> Используется: handlers/navigation, handlers/customer
└─> Не зависит ни от чего

quiz_manager
├─> Используется: handlers/quiz, main
└─> Использует: config

web_server
├─> Используется: main
└─> Использует: config

bot_notifications
├─> Используется: main
└─> Использует: config
```

---

## ✅ Итого

**13 файлов, каждый с одной задачей:**
- 1 точка входа (main.py)
- 3 конфига (config, resources_loader, .env)
- 5 утилит (utils, keyboards, crm_client, menu_manager, quiz_manager)
- 2 инфраструктуры (web_server, bot_notifications)
- 4 хендлера (navigation, customer, quiz, sections)
- 4 документа (README, MIGRATION, ARCHITECTURE, FILES_GUIDE)
- 4 ресурса (JSON)

Все файлы готовы к использованию!
