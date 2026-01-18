# main.py
import os
import re
import time
import asyncio
import urllib.parse
from enum import Enum
from typing import Optional, Dict, Any, List

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

load_dotenv()

# ---- Environment variables ----
BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
ALFA_EMAIL = (os.getenv("ALFA_EMAIL") or "").strip()
ALFA_API_KEY = (os.getenv("ALFA_API_KEY") or "").strip()
COORDINATOR_USERNAME = (os.getenv("COORDINATOR_USERNAME") or "").strip()
ALFA_BASE = (os.getenv("ALFA_BASE") or "").strip().rstrip("/")
PORT = int(os.getenv("PORT", "8000"))

if not COORDINATOR_USERNAME:
    raise RuntimeError("COORDINATOR_USERNAME is not set")
if not ALFA_BASE:
    raise RuntimeError("ALFA_BASE is not set")
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
if not ALFA_EMAIL or not ALFA_API_KEY:
    raise RuntimeError("ALFA_EMAIL / ALFA_API_KEY is not set")

LOGIN_URL = f"{ALFA_BASE}/v2api/auth/login"
CUSTOMER_INDEX_URL = f"{ALFA_BASE}/v2api/3/customer/index"
SWIMMING_BASE_URL = (os.getenv("SWIMMING_BASE_URL") or "").strip()
if not SWIMMING_BASE_URL:
    raise RuntimeError("SWIMMING_BASE_URL is not set")

# ---- UI labels ----
BTN_SWIMMING = "💙️ SWIMMING"
BTN_RUNNING = "💚 RUNNING"
BTN_TRIATHLON = "💜️ TRIATHLON"
BTN_BACK = "Назад"
BTN_WRITE_COORDINATOR = "Написать координатору"
BTN_LESSON_REMAINDER = "Остаток занятий"
BTN_SW_LEVEL = "Узнать свой уровень"
BTN_SW_CERT = "Где получить справку для бассейна"
BTN_SW_PREP = "Как подготовиться к тренировке"
BTN_SW_TAKE = "Что взять с собой в бассейн"

# ---- Section enum ----
class Section(str, Enum):
    SWIMMING = "swimming"
    RUNNING = "running"
    TRIATHLON = "triathlon"

SECTION_TITLES: Dict[Section, str] = {
    Section.SWIMMING: "Плавание",
    Section.RUNNING: "Бег",
    Section.TRIATHLON: "Триатлон",
}

HELLO_BY_SECTION: Dict[Section, str] = {
    Section.SWIMMING: "💙 Привет! Вопрос по направлению Плавание.",
    Section.RUNNING: "💚 Привет! Вопрос по направлению Бег.",
    Section.TRIATHLON: "💜 Привет! Вопрос по направлению Триатлон.",
}

# ---- Swimming level quiz questions ----
SWIMMING_LEVEL_QUESTIONS = [
    {
        "question": "1️⃣ Какой формат занятий Вас интересует?",
        "answers": {
            "group": ("Групповые занятия", "group"),
            "personal": ("Персональные тренировки", "personal"),
        }
    },
    {
        "question": "2️⃣ Какой у Вас опыт плавания?",
        "answers": {
            "a": ("Никогда не плавал / боюсь воды", 0),
            "b": ("Плавал, но без тренера", 1),
            "c": ("Занимался с тренером раньше", 2),
        }
    },
    {
        "question": "3️⃣ Какое расстояние Вы можете проплыть без остановки?",
        "answers": {
            "a": ("Меньше 50 м", 0),
            "b": ("50–300 м", 1),
            "c": ("Более 300 м", 2),
        }
    },
    {
        "question": "4️⃣ Умеете ли Вы плавать кролем?",
        "answers": {
            "a": ("Нет / не знаю техники", 0),
            "b": ("Частично", 1),
            "c": ("Хорошо владею техникой", 2),
        }
    },
    {
        "question": "5️⃣ Какова Ваша цель?",
        "answers": {
            "a": ("Побороть страхи, освоить воду", 0),
            "b": ("Научиться плавать красиво и технично", 1),
            "c": ("Подготовка к заплывам / триатлону", 2),
        }
    },
    {
        "question": "6️⃣ Как часто Вы тренируетесь?",
        "answers": {
            "a": ("Редко или не тренируюсь", 0),
            "b": ("1–2 раза в неделю", 1),
            "c": ("3+ раза в неделю / серьёзно занимаюсь", 2),
        }
    },
]

LEVEL_RESULTS = {
    (0, 2): (
        "🌊 <b>Level 0 — Школа плавания для начинающих</b>",
        "Для тех, кто никогда не плавал, боится бассейнов и открытых водоемов. "
        "Здесь вы победите свои страхи и сделаете первые шаги в мире плавания! 💪"
    ),
    (3, 6): (
        "🏊 <b>Level 1 — Школа плавания с нуля</b>",
        "Для тех, кто хочет научиться красиво и технично плавать. "
        "Мы научим вас правильной технике кроля и основам безопасности. ✨"
    ),
    (7, 9): (
        "🎯 <b>Level 2 — Совершенствование техники</b>",
        "Для тех, кто уже прошел Level 1 или может проплыть 300м кролем. "
        "Совершенствуем технику, работаем над скоростью и выносливостью. 🚀"
    ),
    (10, 15): (
        "⭐ <b>Masters — Подготовка к заплывам и триатлону</b>",
        "Для тех, кто готов к заплывам любой сложности и триатлонным гонкам. "
        "Подойдёт Вам, если Вы уверенно выплываете 1000м из 22 минут. 🏆"
    ),
}

LEVEL_PATHS = {
    (0, 2): "/school-level-0",      # Level 0
    (3, 6): "/level1new",           # Level 1
    (7, 9): "/level_2",             # Level 2
    (10, 15): "/masters-a2208b9e-8a66-4f7a-b2db-d9ea6b59965b",   # Masters
}

PERSONAL_TRAINING_TEXT = (
    "<b>Персональные тренировки</b>\n\n"
    "Персональные тренировки подойдут вам, если:\n"
    "• Вы не можете заниматься в группе\n"
    "• В вашем городе нет филиала I Love Swimming\n"
    "• Вам нужен индивидуальный подход\n\n"
    "Хотите записаться? Напишите координатору ➤"
)

SW_TAKE_TEXT = (
    "<b>Что взять с собой в бассейн:</b>\n"
    "• купальник/плавки для купания\n"
    "• очки для плавания\n"
    "• шапочка\n"
    "• сланцы\n"
    "• полотенце\n"
    "• принадлежности для душа\n"
    "• справка"
)

SW_CERT_TEXT = (
    "<b>Где получить справку?</b>\n\n"
    "• В бассейне перед тренировкой — <b>70 ₽</b>\n"
    "• В вашей поликлинике у терапевта — <b>бесплатно</b>\n"
    "• В медучреждениях, специализирующихся на справках — <b>от 500 ₽</b>"
)

# ---- Utility functions ----
def normalize_ru_phone_to_plus7(text: str) -> Optional[str]:
    """Нормализует российский номер в формат 7XXXXXXXXXX (без плюса)."""
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
    return Section(raw)

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
def kb_root_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BTN_SWIMMING,
                    callback_data="nav:section:swimming",
                )
            ],
            [
                InlineKeyboardButton(
                    text=BTN_RUNNING,
                    callback_data="nav:section:running",
                )
            ],
            [
                InlineKeyboardButton(
                    text=BTN_TRIATHLON,
                    callback_data="nav:section:triathlon",
                )
            ],
        ]
    )

def kb_section_inline(section: Section) -> InlineKeyboardMarkup:
    hello = HELLO_BY_SECTION.get(section, "Привет! Напишите координатору.")
    link = coordinator_link(hello)
    s = section.value
    keyboard = [
        [
            InlineKeyboardButton(
                text=BTN_WRITE_COORDINATOR,
                url=link,
            )
        ],
        [
            InlineKeyboardButton(
                text=BTN_LESSON_REMAINDER,
                callback_data=f"act:lesson_remainder:{s}",
            )
        ],
    ]
    if section == Section.SWIMMING:
        keyboard.extend(
            [
                [
                    InlineKeyboardButton(
                        text=BTN_SW_LEVEL,
                        callback_data="sw:level",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BTN_SW_CERT,
                        callback_data="sw:cert",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BTN_SW_PREP,
                        callback_data="sw:prep",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=BTN_SW_TAKE,
                        callback_data="sw:take",
                    )
                ],
            ]
        )

    keyboard.append(
        [InlineKeyboardButton(text=BTN_BACK, callback_data="nav:root")]
    )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_question_keyboard(q_data: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Клавиатура для вопроса квиза"""
    if q_data["question"].startswith("1️⃣"):
        buttons = [
            [InlineKeyboardButton(text="👥 Групповые занятия", callback_data="quiz:format:group")],
            [InlineKeyboardButton(text="👤 Персональные тренировки", callback_data="quiz:format:personal")],
        ]
    else:
        buttons = [
            [InlineKeyboardButton(text=f"А) {q_data['answers']['a'][0]}", callback_data="quiz:answer:a")],
            [InlineKeyboardButton(text=f"Б) {q_data['answers']['b'][0]}", callback_data="quiz:answer:b")],
            [InlineKeyboardButton(text=f"В) {q_data['answers']['c'][0]}", callback_data="quiz:answer:c")],
        ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ---- Menu management ----
async def ensure_menu_message(
    m: Message,
    menu_msg_id_by_user: Dict[int, int],
    text: str,
    markup: InlineKeyboardMarkup,
) -> None:
    """Гарантирует одно меню-сообщение: если есть — редактируем, иначе создаём."""
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

def title_root() -> str:
    return "Выберите направление:"

def title_section(section: Section) -> str:
    title = SECTION_TITLES.get(section, section.value)
    return f"{title}. Выберите действие:"

# ---- HTTP server for Render ----
async def handle_root(request: web.Request) -> web.Response:
    return web.Response(text="Sports Bot OK\n")

async def start_web_app() -> None:
    app = web.Application()
    app.add_routes([web.get("/", handle_root)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    await site.start()
    print(f"Web server listening on port {PORT}")
    while True:
        await asyncio.sleep(3600)

# ---- Bot handlers ----
async def run_bot() -> None:
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    alfa = AlfaCRMClient(ALFA_EMAIL, ALFA_API_KEY)

    menu_msg_id_by_user: Dict[int, int] = {}
    waiting_phone_section_by_user: Dict[int, Section] = {}
    quiz_state: Dict[int, Dict[str, Any]] = {}

    # ---- Swimming level quiz handlers ----
    @dp.callback_query(F.data == "sw:level")
    async def sw_level_start(cq: CallbackQuery):
        uid = cq.from_user.id
        await cq.answer()
        quiz_state[uid] = {"question_idx": 0, "score": 0, "format": None}
        q_data = SWIMMING_LEVEL_QUESTIONS[0]
        await cq.message.answer(q_data["question"], reply_markup=get_question_keyboard(q_data))

    @dp.callback_query(F.data.startswith("quiz:format:"))
    async def quiz_format_choice(cq: CallbackQuery):
        uid = cq.from_user.id
        if uid not in quiz_state:
            await cq.answer("Квиз не начинался. Нажми 'Узнать свой уровень'")
            return
        format_choice = cq.data.split(":")[-1]
        quiz_state[uid]["format"] = format_choice
        await cq.answer()
        if format_choice == "personal":

            # Кнопки действий
            hello = HELLO_BY_SECTION[Section.SWIMMING]
            coordinator_url = coordinator_link(f"{hello} Интересуют персональные тренировки")
            
            buttons = [
                [InlineKeyboardButton(text="💬 Написать координатору", url=coordinator_url)],
            ]
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            await cq.message.answer(PERSONAL_TRAINING_TEXT, reply_markup=markup, parse_mode="HTML")
            quiz_state.pop(uid, None)
            return
        quiz_state[uid]["question_idx"] += 1
        next_q = SWIMMING_LEVEL_QUESTIONS[quiz_state[uid]["question_idx"]]
        await cq.message.answer(next_q["question"], reply_markup=get_question_keyboard(next_q))

    @dp.callback_query(F.data.startswith("quiz:answer:"))
    async def quiz_answer(cq: CallbackQuery):
        uid = cq.from_user.id
        if uid not in quiz_state:
            await cq.answer("Квиз не начинался. Нажми 'Узнать свой уровень'")
            return
        answer_key = cq.data.split(":")[-1]
        q_idx = quiz_state[uid]["question_idx"]
        q_data = SWIMMING_LEVEL_QUESTIONS[q_idx]
        score = q_data["answers"][answer_key][1]
        quiz_state[uid]["score"] += score
        await cq.answer()
        quiz_state[uid]["question_idx"] += 1
        next_idx = quiz_state[uid]["question_idx"]
        if next_idx < len(SWIMMING_LEVEL_QUESTIONS):
            next_q = SWIMMING_LEVEL_QUESTIONS[next_idx]
            await cq.message.answer(next_q["question"], reply_markup=get_question_keyboard(next_q))
        else:
            total_score = quiz_state[uid]["score"]
            level_title, level_desc = "🌊 Level 0", "Неизвестный уровень"
            level_url = SWIMMING_BASE_URL
            for (min_s, max_s), (title, desc) in LEVEL_RESULTS.items():
                if min_s <= total_score <= max_s:
                    level_title, level_desc = title, desc
                    level_path = LEVEL_PATHS[(min_s, max_s)]
                    level_url = f"{SWIMMING_BASE_URL}{level_path}"
                    break
            result_text = (
                f"<b>Результат вашего теста:</b>\n\n"
                f"{level_title}\n\n"
                f"{level_desc}\n\n"
                f"<i>Баллы: {total_score}/12</i>\n\n"
                f"<b>Готовы начать?</b> Напишите координатору! ➤"
            )

            # Кнопки действий
            hello = HELLO_BY_SECTION[Section.SWIMMING]
            coordinator_url = coordinator_link(f"{hello} Интересует {level_title}")
            
            buttons = [
                [InlineKeyboardButton(text="📖 Подробнее о программе", url=level_url)],
                [InlineKeyboardButton(text="💬 Написать координатору", url=coordinator_url)],
            ]
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            await cq.message.answer(result_text, reply_markup=markup, parse_mode="HTML")
            
            # Очистим состояние
            quiz_state.pop(uid, None)

    # ---- Swimming section handlers ----
    @dp.callback_query(F.data == "sw:cert")
    async def sw_cert(cq: CallbackQuery):
        await cq.answer()
        await cq.message.answer(
            SW_CERT_TEXT,
            parse_mode="HTML"
        )

    @dp.callback_query(F.data == "sw:prep")
    async def sw_prep(cq: CallbackQuery):
        await cq.answer()
        await cq.message.answer("Инструкция по подготовке скоро появится!")

    @dp.callback_query(F.data == "sw:take")
    async def sw_take(cq: CallbackQuery):
        await cq.answer()
        await cq.message.answer(
            SW_TAKE_TEXT,
            parse_mode="HTML"
        )

    # ---- Main navigation handlers ----
    @dp.message(CommandStart())
    async def start(m: Message):
        waiting_phone_section_by_user.pop(m.from_user.id, None)
        await ensure_menu_message(
            m,
            menu_msg_id_by_user,
            title_root(),
            kb_root_inline(),
        )

    @dp.callback_query(F.data == "nav:root")
    async def nav_root(cq: CallbackQuery):
        waiting_phone_section_by_user.pop(cq.from_user.id, None)
        await edit_menu_message(
            cq,
            menu_msg_id_by_user,
            title_root(),
            kb_root_inline(),
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
            cq,
            menu_msg_id_by_user,
            text=(
                "Отправьте номер телефона РФ одним сообщением.\n"
                "Примеры: +7 912 345-67-89, 89123456789, 79123456789."
            ),
            markup=kb_section_inline(section),
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
                kb_root_inline(),
            )
            return
        phone = normalize_ru_phone_to_plus7(m.text or "")
        if not phone:
            await m.answer(
                "Неверный формат телефона.\n"
                "Примеры: +7 912 345-67-89, 89123456789, 79123456789."
            )
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
                    m,
                    menu_msg_id_by_user,
                    text=(
                        "Клиент с таким номером не найден.\n"
                        "Если уверены, что все верно, напишите координатору по кнопке выше."
                    ),
                    markup=kb_section_inline(section),
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
        except Exception:
            await ensure_menu_message(
                m,
                menu_msg_id_by_user,
                text=(
                    "Сервис проверки остатка занятий сейчас недоступен.\n"
                    "Пожалуйста, напишите координатору по кнопке выше."
                ),
                markup=kb_section_inline(section),
            )

    print("Starting Telegram bot polling...")
    await dp.start_polling(bot)

async def main():
    """
    Запускает параллельно:
    - Telegram бот (polling)
    - HTTP сервер для Render (открытый порт)
    """
    bot_task = asyncio.create_task(run_bot())
    web_task = asyncio.create_task(start_web_app())
    await asyncio.gather(bot_task, web_task)

if __name__ == "__main__":
    asyncio.run(main())