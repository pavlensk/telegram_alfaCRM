# main.py
import os
import re
import json
import time
import asyncio
import urllib.parse
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

import httpx
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.filters import CommandStart
from dotenv import load_dotenv

import signal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# ---- Resource Loader ----
class Resources:
    """Загрузчик ресурсных файлов."""
    RESOURCES_DIR = Path(__file__).parent / "resources"
    
    @classmethod
    def load(cls, filename: str) -> Dict:
        """Загружает JSON ресурс."""
        path = cls.RESOURCES_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"Resource not found: {path}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"✅ Loaded resource: {filename}")
                return data
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON in {filename}: {e}")

# Инициализация ресурсов при старте
try:
    UI_LABELS = Resources.load("ui_labels.json")
    SECTIONS = Resources.load("sections.json")
    QUIZ_DATA = Resources.load("quiz_questions.json")
    TEXTS = Resources.load("texts.json")
    logger.info("✅ All resources loaded successfully")
except (FileNotFoundError, RuntimeError) as e:
    logger.error(f"❌ Failed to load resources: {e}")
    raise
# ---- Environment variables ----
BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
ALFA_EMAIL = (os.getenv("ALFA_EMAIL") or "").strip()
ALFA_API_KEY = (os.getenv("ALFA_API_KEY") or "").strip()
COORDINATOR_USERNAME = (os.getenv("COORDINATOR_USERNAME") or "").strip()
ALFA_BASE = (os.getenv("ALFA_BASE") or "").strip().rstrip("/")
PORT = int(os.getenv("PORT", "8000"))
BOT_STATUS_CHAT_ID = int(os.getenv("BOT_STATUS_CHAT_ID", "0"))
SWIMMING_BASE_URL = (os.getenv("SWIMMING_BASE_URL") or "").strip()
LOGIN_URL = f"{ALFA_BASE}/v2api/auth/login"
CUSTOMER_INDEX_URL = f"{ALFA_BASE}/v2api/3/customer/index"

REQUIRED_ENVS = [
    ("COORDINATOR_USERNAME", COORDINATOR_USERNAME),
    ("ALFA_BASE", ALFA_BASE),
    ("TELEGRAM_BOT_TOKEN", BOT_TOKEN),
    ("ALFA_EMAIL", ALFA_EMAIL),
    ("ALFA_API_KEY", ALFA_API_KEY),
    ("SWIMMING_BASE_URL", SWIMMING_BASE_URL),
	("LOGIN_URL", LOGIN_URL),
	("CUSTOMER_INDEX_URL", CUSTOMER_INDEX_URL)
]

for env_name, value in REQUIRED_ENVS:
    if not value:
        raise RuntimeError(f"{env_name} is not set")

# ---- Parse quiz data ----
SWIMMING_LEVEL_QUESTIONS = QUIZ_DATA["questions"]
QUIZ_TTL_SECONDS = QUIZ_DATA["quiz_ttl_seconds"]

# Парсим индексы вопросов
QUIZ_IDX_FORMAT = QUIZ_DATA["quiz_indices"]["format"]
QUIZ_IDX_EXPERIENCE = QUIZ_DATA["quiz_indices"]["experience"]
QUIZ_IDX_DISTANCE = QUIZ_DATA["quiz_indices"]["distance"]
QUIZ_IDX_FREESTYLE = QUIZ_DATA["quiz_indices"]["freestyle"]
QUIZ_IDX_GOAL = QUIZ_DATA["quiz_indices"]["goal"]

# Преобразуем level_results в нужный формат
LEVEL_RESULTS: Dict[Tuple[int, int], Tuple[str, str]] = {}
LEVEL_PATHS: Dict[Tuple[int, int], str] = {}

for key_str, data in QUIZ_DATA["level_results"].items():
    # Парсим "(min,max)" в кортеж (min, max)
    clean_key = key_str.strip("()")
    min_score, max_score = map(int, clean_key.split(","))
    key = (min_score, max_score)
    
    LEVEL_RESULTS[key] = (data["title"], data["desc"])
    LEVEL_PATHS[key] = data["path"]
# ---- Section enum ----
class Section(str, Enum):
    SWIMMING = "swimming"
    RUNNING = "running"
    TRIATHLON = "triathlon"

# Получаем секции из ресурсов
SECTION_TITLES: Dict[Section, str] = {
    Section(k): v["title"] 
    for k, v in SECTIONS["sections"].items()
}

HELLO_BY_SECTION: Dict[Section, str] = {
    Section(k): v["hello"] 
    for k, v in SECTIONS["sections"].items()
}

# ---- Utility functions ----
def normalize_ru_phone_to_plus7(text: str) -> Optional[str]:
    """Нормализует российский номер в формат 7XXXXXXXXXX."""
    digits = re.sub(r"\D", "", text or "")
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 10 and digits.startswith("9"):
        digits = "7" + digits
    if len(digits) == 11 and digits.startswith("7"):
        return digits
    return None

def coordinator_link(start_text: str) -> str:
    return (
        f"https://t.me/{COORDINATOR_USERNAME}"
        f"?text={urllib.parse.quote(start_text)}"
    )

def parse_section(raw: str) -> Section:
    """Парсит секцию из callback_data."""
    return Section(raw)

def title_root() -> str:
    """Заголовок главного меню."""
    return "Выберите направление:"

def title_section(section: Section) -> str:
    """Заголовок меню секции."""
    title = SECTION_TITLES.get(section, section.value)
    return f"{title}. Выберите действие:"

# ---- AlfaCRM client ----
class AlfaCRMClient:
    def __init__(self, email: str, apikey: str):
        self.email = email
        self.apikey = apikey
        self.token: Optional[str] = None
        self.token_ts: float = 0.0
        self.lock = asyncio.Lock()

    async def login(self, client: httpx.AsyncClient) -> str:
        payload = {"email": self.email, "api_key": self.apikey}
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        r = await client.post(LOGIN_URL, json=payload, headers=headers, timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f"Login failed HTTP {r.status_code}: {r.text}")
        data = r.json()
        token = data.get("token")
        if not token:
            raise RuntimeError(f"Login response has no token: {data}")
        self.token = token
        self.token_ts = time.time()
        return token

    async def get_token(self, client: httpx.AsyncClient) -> str:
        async with self.lock:
            if self.token and (time.time() - self.token_ts) < 12 * 3600:
                return self.token
            return await self.login(client)

    async def customer_search_by_phone(self, phone_plus7: str) -> Dict[str, Any]:
        """Поиск клиента по телефону."""
        async with httpx.AsyncClient() as client:
            token = await self.get_token(client)
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-ALFACRM-TOKEN": token,
            }
            payload = {"phone": phone_plus7}

            r = await client.post(
                CUSTOMER_INDEX_URL,
                json=payload,
                headers=headers,
                timeout=20,
            )

            if r.status_code in (401, 403):
                async with self.lock:
                    self.token = None
                    self.token_ts = 0.0
                token = await self.get_token(client)
                headers["X-ALFACRM-TOKEN"] = token
                r = await client.post(
                    CUSTOMER_INDEX_URL,
                    json=payload,
                    headers=headers,
                    timeout=20,
                )

            if r.status_code != 200:
                raise RuntimeError(
                    f"customer/index failed HTTP {r.status_code}: {r.text}"
                )

            return r.json()

def extract_customer_fields(resp: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Извлекает поля клиента из ответа AlfaCRM."""
    items: List[Dict[str, Any]] = resp.get("items") or []
    if not items:
        return None
    c = items[0] or {}
    return {
        "legal_name": c.get("legal_name") or "",
        "balance": c.get("balance"),
        "paid_lesson_count": c.get("paid_lesson_count"),
    }

# ---- Inline keyboards ----
def kb_root_inline(ui_labels: dict) -> InlineKeyboardMarkup:
    """Главное меню."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=ui_labels["btn_swimming"],  # ✅ Правильно!
                    callback_data="nav:section:swimming"
                )
            ],
            [
                InlineKeyboardButton(
                    text=ui_labels["btn_running"],   # ✅ Правильно!
                    callback_data="nav:section:running"
                )
            ],
            [
                InlineKeyboardButton(
                    text=ui_labels["btn_triathlon"], # ✅ Правильно!
                    callback_data="nav:section:triathlon"
                )
            ]
        ]
    )

def kb_section_inline(section: Section) -> InlineKeyboardMarkup:
    """Меню секции."""
    hello = HELLO_BY_SECTION.get(section, "Привет! Напишите координатору.")
    link = coordinator_link(hello)
    s = section.value
    keyboard = [
        [
            InlineKeyboardButton(
                text=UI_LABELS["btn_write_coordinator"],
                url=link,
            )
        ],
        [
            InlineKeyboardButton(
                text=UI_LABELS["btn_lesson_remainder"],
                callback_data=f"act:lesson_remainder:{s}",
            )
        ],
    ]
    if section == Section.SWIMMING:
        keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        text=UI_LABELS["btn_sw_level"],
                        callback_data="sw:level",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=UI_LABELS["btn_sw_cert"],
                        callback_data="sw:cert",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=UI_LABELS["btn_sw_prep"],
                        callback_data="sw:prep",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=UI_LABELS["btn_sw_take"],
                        callback_data="sw:take",
                    )
                ],
            ]
        )

    keyboard.append(
        [InlineKeyboardButton(text=UI_LABELS["btn_back"], callback_data="nav:root")]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_question_keyboard_adaptive(
    q_data: Dict[str, Any], 
    uid: int = None, 
    quiz_state: Optional[Dict[int, Dict]] = None
) -> InlineKeyboardMarkup:
    """Универсальная клавиатура для любого вопроса квиза."""
    buttons = []
    answers_keys = list(q_data["answers"].keys())
    
    # Для вопроса 5 скрываем вариант "a" если score > 2
    if q_data["question"].startswith("5️⃣") and uid and quiz_state and uid in quiz_state:
        score = quiz_state[uid]["score"]
        if score > 2:
            answers_keys = [k for k in answers_keys if k != "a"]
    
    # Динамическая нумерация А) Б) В)
    letter_map = {0: "А)", 1: "Б)", 2: "В)"}
    for idx, key in enumerate(answers_keys):
        text = q_data["answers"][key][0]
        buttons.append([InlineKeyboardButton(
            text=f"{letter_map[idx]} {text}", 
            callback_data=f"quiz:answer:{key}"
        )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ---- Menu management ----
async def ensure_menu_message(
    m: Message,
    menu_msg_id_by_user: Dict[int, int],
    text: str,
    markup: InlineKeyboardMarkup,
) -> None:
    """Гарантирует одно меню-сообщение."""
    uid = m.from_user.id
    msg_id = menu_msg_id_by_user.get(uid)
    if msg_id:
        try:
            await m.bot.edit_message_text(
                chat_id=m.chat.id,
                message_id=msg_id,
                text=text,
                reply_markup=markup,
            )
            return
        except Exception:
            pass
    sent = await m.answer(text, reply_markup=markup)
    menu_msg_id_by_user[uid] = sent.message_id

async def edit_menu_message(
    cq: CallbackQuery,
    menu_msg_id_by_user: Dict[int, int],
    text: str,
    markup: InlineKeyboardMarkup,
) -> None:
    """Редактирует меню в callback."""
    uid = cq.from_user.id
    await cq.answer()
    msg_id = menu_msg_id_by_user.get(uid)
    if msg_id:
        try:
            await cq.bot.edit_message_text(
                chat_id=cq.message.chat.id,
                message_id=msg_id,
                text=text,
                reply_markup=markup,
            )
            return
        except Exception:
            pass
    try:
        await cq.message.edit_text(text, reply_markup=markup)
        menu_msg_id_by_user[uid] = cq.message.message_id
    except Exception:
        sent = await cq.message.answer(text, reply_markup=markup)
        menu_msg_id_by_user[uid] = sent.message_id

# ---- HTTP server ----
async def handle_root(request: web.Request) -> web.Response:
    return web.Response(text="Sports Bot OK\n")

async def start_web_app() -> None:
    app = web.Application()
    app.add_routes([web.get("/", handle_root)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Web server listening on port {PORT}")
    while True:
        await asyncio.sleep(3600)

# ---- Bot handlers ----
async def run_bot(bot: Bot) -> None:
    dp = Dispatcher()
    alfa = AlfaCRMClient(ALFA_EMAIL, ALFA_API_KEY)

    menu_msg_id_by_user: Dict[int, int] = {}
    waiting_phone_section_by_user: Dict[int, Section] = {}
    quiz_state: Dict[int, Dict[str, Any]] = {}

    def validate_quiz_state(uid: int) -> bool:
        """Проверяет валидность quiz_state с TTL."""
        if uid not in quiz_state:
            return False
        if time.time() - quiz_state[uid]["timestamp"] > QUIZ_TTL_SECONDS:
            quiz_state.pop(uid, None)
            return False
        return True

    def adaptive_next_question(uid: int, current_q_idx: int, current_answer: str) -> int:
        """Возвращает индекс следующего вопроса или len() для завершения."""
        state = quiz_state[uid]
        q_data = SWIMMING_LEVEL_QUESTIONS[current_q_idx]
        
        if current_answer not in q_data["answers"]:
            logger.error(f"Invalid answer '{current_answer}' for question {current_q_idx}")
            return len(SWIMMING_LEVEL_QUESTIONS)
        
        score = q_data["answers"][current_answer][1]
        state["score"] += score
        
        # Адаптивная логика переходов
        if current_q_idx == QUIZ_IDX_FORMAT:
            if current_answer == "b":  # Персональные
                return len(SWIMMING_LEVEL_QUESTIONS)
        
        elif current_q_idx == QUIZ_IDX_EXPERIENCE:
            if current_answer in ("a", "c"):
                return QUIZ_IDX_FREESTYLE  # Пропускаем расстояние
        
        elif current_q_idx == QUIZ_IDX_DISTANCE:
            if current_answer == "a":
                return QUIZ_IDX_GOAL  # Пропускаем кроль
        
        return current_q_idx + 1

    async def show_quiz_result(cq: CallbackQuery, uid: int) -> None:
        """Показывает результат квиза."""
        total_score = quiz_state[uid]["score"]
        
        level_title, level_desc = "🌊 Level 0", "Неизвестный уровень"
        level_url = SWIMMING_BASE_URL
        
        for (min_s, max_s), (title, desc) in LEVEL_RESULTS.items():
            if min_s <= total_score <= max_s:
                level_title, level_desc = title, desc
                if min_s != -1:
                    level_path = LEVEL_PATHS.get((min_s, max_s), "")
                    level_url = f"{SWIMMING_BASE_URL}{level_path}"
                break
        
        result_text = (
            f"<b>Результат вашего теста:</b>\n\n"
            f"<b>{level_title}</b>\n\n{level_desc}\n\n"
        )
        
        if total_score != -1:
            result_text += f"<i>Баллы: {total_score}/8</i>\n\n"
        
        result_text += "<b>Готовы начать?</b> Напишите координатору! ➤"
        
        hello = HELLO_BY_SECTION[Section.SWIMMING]
        coordinator_url = coordinator_link(f"{hello} Интересует {level_title}")
        
        buttons = [
            [InlineKeyboardButton(text="📖 Подробнее о программе", url=level_url)],
            [InlineKeyboardButton(text="💬 Написать координатору", url=coordinator_url)],
        ]
        
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        await cq.message.answer(result_text, reply_markup=markup, parse_mode="HTML")

    # Swimming level quiz handlers
    @dp.callback_query(F.data == "sw:level")
    async def sw_level_start(cq: CallbackQuery):
        uid = cq.from_user.id
        await cq.answer()
        quiz_state[uid] = {
            "question_idx": QUIZ_IDX_FORMAT,
            "score": 0,
            "timestamp": time.time(),
        }
        q_data = SWIMMING_LEVEL_QUESTIONS[QUIZ_IDX_FORMAT]
        await cq.message.answer(
            q_data["question"],
            reply_markup=get_question_keyboard_adaptive(q_data, uid, quiz_state)
        )

    @dp.callback_query(F.data.startswith("quiz:answer:"))
    async def quiz_answer(cq: CallbackQuery):
        uid = cq.from_user.id
        if not validate_quiz_state(uid):
            await cq.answer(TEXTS["quiz_expired"])
            return
        
        answer_key = cq.data.split(":")[-1]
        q_idx = quiz_state[uid]["question_idx"]
        
        await cq.answer()
        next_idx = adaptive_next_question(uid, q_idx, answer_key)
        quiz_state[uid]["question_idx"] = next_idx
        
        if next_idx >= len(SWIMMING_LEVEL_QUESTIONS):
            await show_quiz_result(cq, uid)
            quiz_state.pop(uid, None)
        else:
            next_q = SWIMMING_LEVEL_QUESTIONS[next_idx]
            await cq.message.answer(
                next_q["question"],
                reply_markup=get_question_keyboard_adaptive(next_q, uid, quiz_state)
            )

    # Swimming section handlers
    @dp.callback_query(F.data == "sw:cert")
    async def sw_cert(cq: CallbackQuery):
        await cq.answer()
        await cq.message.answer(
            TEXTS["sw_cert"],
            parse_mode="HTML"
        )

    @dp.callback_query(F.data == "sw:prep")
    async def sw_prep(cq: CallbackQuery):
        await cq.answer()
        await cq.message.answer(TEXTS["sw_prep"])

    @dp.callback_query(F.data == "sw:take")
    async def sw_take(cq: CallbackQuery):
        await cq.answer()
        await cq.message.answer(
            TEXTS["sw_take"],
            parse_mode="HTML"
        )

    # Main navigation handlers
    @dp.message(CommandStart())
    async def start(m: Message):
        waiting_phone_section_by_user.pop(m.from_user.id, None)
        await ensure_menu_message(
            m,
            menu_msg_id_by_user,
            title_root(),
            kb_root_inline(UI_LABELS),
        )

    @dp.callback_query(F.data == "nav:root")
    async def nav_root(cq: CallbackQuery):
        waiting_phone_section_by_user.pop(cq.from_user.id, None)
        await edit_menu_message(
            cq,
            menu_msg_id_by_user,
            title_root(),
            kb_root_inline(UI_LABELS),
        )

    @dp.callback_query(F.data.startswith("nav:section:"))
    async def nav_section(cq: CallbackQuery):
        waiting_phone_section_by_user.pop(cq.from_user.id, None)
        raw = (cq.data or "").split(":")[-1]
        section = parse_section(raw)
        await edit_menu_message(
            cq,
            menu_msg_id_by_user,
            title_section(section),
            kb_section_inline(section),
        )

    @dp.callback_query(F.data.startswith("act:lesson_remainder:"))
    async def act_lesson_remainder(cq: CallbackQuery):
        raw = (cq.data or "").split(":")[-1]
        section = parse_section(raw)
        waiting_phone_section_by_user[cq.from_user.id] = section
        await edit_menu_message(
            cq, menu_msg_id_by_user,
            TEXTS["invalid_phone"],
            kb_section_inline(section),
        )

    @dp.message(F.text)
    async def handle_text(m: Message):
        uid = m.from_user.id
        section = waiting_phone_section_by_user.get(uid)
        if section is None:
            await ensure_menu_message(
                m,
                menu_msg_id_by_user,
                title_root(),
                kb_root_inline(UI_LABELS),
            )
            return
        
        phone = normalize_ru_phone_to_plus7(m.text or "")
        if not phone:
            await m.answer(TEXTS["invalid_phone"])
            return
        
        waiting_phone_section_by_user.pop(uid, None)
        await ensure_menu_message(
            m,
            menu_msg_id_by_user,
            text=f"Ищу клиента по номеру: +{phone}",
            markup=kb_section_inline(section),
        )

        try:
            resp = await alfa.customer_search_by_phone(phone)
            customer = extract_customer_fields(resp)
            if not customer:
                await ensure_menu_message(
                    m, menu_msg_id_by_user,
                    TEXTS["client_not_found"],
                    kb_section_inline(section),
                )
                return
            
            legal_name = customer.get("legal_name") or "—"
            balance_txt = str(customer.get("balance")) if customer.get("balance") is not None else "—"
            paid_txt = str(customer.get("paid_lesson_count")) if customer.get("paid_lesson_count") is not None else "—"
            
            await ensure_menu_message(
                m,
                menu_msg_id_by_user,
                text=(
                    f"Клиент: {legal_name}\n"
                    f"Баланс: {balance_txt}\n"
                    f"Оплаченных уроков: {paid_txt}"
                ),
                markup=kb_section_inline(section),
            )
        except Exception as e:
            logger.error(f"AlfaCRM search failed for phone {phone}: {type(e).__name__}: {e}")
            await ensure_menu_message(
                m, menu_msg_id_by_user,
                TEXTS["service_unavailable"],
                kb_section_inline(section),
            )

    await notify_bot_ready(bot)
    logger.info("Starting Telegram bot polling...")
    await dp.start_polling(bot)

async def notify_bot_ready(bot: Bot):
    if not BOT_STATUS_CHAT_ID:
        logger.info("BOT_STATUS_CHAT_ID не задан")
        return
    try:
        await bot.send_message(
            BOT_STATUS_CHAT_ID,
            f"🤖 <b>Sports Bot запущен!</b>\n\n"
            f"🕐 <i>{time.strftime('%Y-%m-%d %H:%M:%S')}</i>\n"
            f"✅ AlfaCRM: OK\n"
            f"✅ Web: порт {PORT}",
            parse_mode="HTML"
        )
        logger.info("✅ Уведомление о запуске отправлено!")
    except Exception as e:
        logger.error(f"Ошибка уведомления о запуске: {type(e).__name__}: {e}")

async def notify_bot_stopped(bot: Bot):
    if not BOT_STATUS_CHAT_ID:
        return
    try:
        await bot.send_message(
            BOT_STATUS_CHAT_ID,
            "🛑 <b>Sports Bot остановлен</b>",
            parse_mode="HTML"
        )
        logger.info("✅ Уведомление об остановке отправлено!")
    except Exception as e:
        logger.error(f"Ошибка уведомления об остановке: {type(e).__name__}: {e}")

async def main():
    bot = Bot(BOT_TOKEN)
    
    bot_task = asyncio.create_task(run_bot(bot))
    web_task = asyncio.create_task(start_web_app())
    
    def handle_shutdown():
        logger.info("Shutdown signal received...")
        bot_task.cancel()
        web_task.cancel()
    
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_shutdown)
    
    try:
        await asyncio.gather(bot_task, web_task)
    except asyncio.CancelledError:
        logger.info("Tasks cancelled")
    finally:
        await notify_bot_stopped(bot)
        await bot.session.close()
        logger.info("Bot session closed")

if __name__ == "__main__":
    asyncio.run(main())
