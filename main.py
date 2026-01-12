# main.py
import os
import re
import time
import asyncio
import urllib.parse
from enum import Enum
from typing import Optional, Dict, Any, List

import httpx
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

BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
ALFA_EMAIL = (os.getenv("ALFA_EMAIL") or "").strip()
ALFA_API_KEY = (os.getenv("ALFA_API_KEY") or "").strip()

COORDINATOR_USERNAME = (os.getenv("COORDINATOR_USERNAME") or "").strip()
if not COORDINATOR_USERNAME:
    raise RuntimeError("COORDINATOR_USERNAME is not set")

ALFA_BASE = (os.getenv("ALFA_BASE") or "").strip().rstrip("/")
if not ALFA_BASE:
    raise RuntimeError("ALFA_BASE is not set")

LOGIN_URL = f"{ALFA_BASE}/v2api/auth/login"
CUSTOMER_INDEX_URL = f"{ALFA_BASE}/v2api/3/customer/index"

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
if not ALFA_EMAIL or not ALFA_API_KEY:
    raise RuntimeError("ALFA_EMAIL / ALFA_API_KEY is not set")

# ---- UI labels ----
BTN_SWIMMING = "🏊‍♂️ Swimming"
BTN_RUNNING = "🏃‍♂️ Running"
BTN_TRIATHLON = "🏊‍♂️🚴‍♂️🏃‍♂️ Triathlon"
BTN_BACK = "Назад"

BTN_WRITE_COORDINATOR = "Написать координатору"
BTN_LESSON_REMAINDER = "Остаток занятий"

class Section(str, Enum):
    SWIMMING = "swimming"
    RUNNING = "running"
    TRIATHLON = "triathlon"

HELLO_BY_SECTION: Dict[Section, str] = {
    Section.SWIMMING: "Привет",
    Section.RUNNING: "Привет",
    Section.TRIATHLON: "Привет",
}

def normalize_ru_phone_to_plus7(text: str) -> Optional[str]:
    digits = re.sub(r"\D", "", text or "")

    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits

    if len(digits) != 11 or not digits.startswith("7"):
        return None
    return digits

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

            r = await client.post(CUSTOMER_INDEX_URL, json=payload, headers=headers, timeout=20)

            # token мог протухнуть
            if r.status_code in (401, 403):
                async with self.lock:
                    self.token = None
                    self.token_ts = 0.0
                token = await self.get_token(client)
                headers["X-ALFACRM-TOKEN"] = token
                r = await client.post(CUSTOMER_INDEX_URL, json=payload, headers=headers, timeout=20)

            if r.status_code != 200:
                raise RuntimeError(f"customer/index failed HTTP {r.status_code}: {r.text}")

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

def coordinator_link(start_text: str) -> str:
    return f"https://t.me/{COORDINATOR_USERNAME}?text={urllib.parse.quote(start_text)}"

# ---- Inline keyboards (callback_data carries section) ----
def kb_root_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_SWIMMING, callback_data="nav:section:swimming")],
            [InlineKeyboardButton(text=BTN_RUNNING, callback_data="nav:section:running")],
            [InlineKeyboardButton(text=BTN_TRIATHLON, callback_data="nav:section:triathlon")],
        ]
    )

def kb_section_inline(section: Section) -> InlineKeyboardMarkup:
    hello = HELLO_BY_SECTION.get(section, "Привет")
    link = coordinator_link(hello)

    s = section.value
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_WRITE_COORDINATOR, url=link)],
            [InlineKeyboardButton(text=BTN_LESSON_REMAINDER, callback_data=f"act:lesson_remainder:{s}")],
            [InlineKeyboardButton(text=BTN_BACK, callback_data="nav:root")],
        ]
    )

def title_root() -> str:
    return "Выберите раздел:"

def title_section(section: Section) -> str:
    return f"Раздел {section.value}. Выберите действие:"

async def ensure_menu_message(
    m: Message,
    menu_msg_id_by_user: Dict[int, int],
    text: str,
    markup: InlineKeyboardMarkup,
) -> None:
    """
    Гарантирует одно “меню-сообщение”: если уже есть — редактируем, иначе создаём.
    """
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
    """
    Редактирует меню в callback. Если callback пришёл не от “того” сообщения — всё равно
    редактируем текущее меню, либо текущее сообщение callback.
    """
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

def parse_section(raw: str) -> Section:
    return Section(raw)  # ValueError если мусор

async def main():
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    alfa = AlfaCRMClient(ALFA_EMAIL, ALFA_API_KEY)

    menu_msg_id_by_user: Dict[int, int] = {}
    waiting_phone_section_by_user: Dict[int, Section] = {}  # uid -> section

    @dp.message(CommandStart())
    async def start(m: Message):
        waiting_phone_section_by_user.pop(m.from_user.id, None)
        await ensure_menu_message(m, menu_msg_id_by_user, title_root(), kb_root_inline())

    @dp.callback_query(F.data == "nav:root")
    async def nav_root(cq: CallbackQuery):
        waiting_phone_section_by_user.pop(cq.from_user.id, None)
        await edit_menu_message(cq, menu_msg_id_by_user, title_root(), kb_root_inline())

    @dp.callback_query(F.data.startswith("nav:section:"))
    async def nav_section(cq: CallbackQuery):
        waiting_phone_section_by_user.pop(cq.from_user.id, None)
        raw = (cq.data or "").split(":")[-1]
        section = parse_section(raw)
        await edit_menu_message(cq, menu_msg_id_by_user, title_section(section), kb_section_inline(section))

    @dp.callback_query(F.data.startswith("act:lesson_remainder:"))
    async def act_lesson_remainder(cq: CallbackQuery):
        raw = (cq.data or "").split(":")[-1]
        section = parse_section(raw)

        waiting_phone_section_by_user[cq.from_user.id] = section
        await edit_menu_message(
            cq,
            menu_msg_id_by_user,
            text="Отправьте номер телефона РФ (например 79123456789 или 89123456789).",
            markup=kb_section_inline(section),
        )

    @dp.message(F.text)
    async def handle_text(m: Message):
        uid = m.from_user.id

        section = waiting_phone_section_by_user.get(uid)
        if section is None:
            # пользователь пишет что-то вне сценария — возвращаем к root-меню без хранения экрана
            await ensure_menu_message(m, menu_msg_id_by_user, title_root(), kb_root_inline())
            return

        phone = normalize_ru_phone_to_plus7(m.text or "")
        if not phone:
            await m.answer("Неверный формат. Пример: 79123456789 или 89123456789.")
            return

        waiting_phone_section_by_user.pop(uid, None)

        await ensure_menu_message(
            m,
            menu_msg_id_by_user,
            text=f"Ищу клиента по номеру: {phone}",
            markup=kb_section_inline(section),
        )

        try:
            resp = await alfa.customer_search_by_phone(phone)
            customer = extract_customer_fields(resp)
            if not customer:
                await ensure_menu_message(
                    m,
                    menu_msg_id_by_user,
                    text="Клиент не найден.",
                    markup=kb_section_inline(section),
                )
                return

            legal_name = customer.get("legal_name") or "—"
            balance = customer.get("balance")
            paid_lesson_count = customer.get("paid_lesson_count")

            balance_txt = str(balance) if balance is not None else "—"
            paid_txt = str(paid_lesson_count) if paid_lesson_count is not None else "—"

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
            await ensure_menu_message(
                m,
                menu_msg_id_by_user,
                text=f"Ошибка при запросе к AlfaCRM: {e}",
                markup=kb_section_inline(section),
            )

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())