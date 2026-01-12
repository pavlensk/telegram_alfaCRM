import os
import re
import time
import asyncio
import urllib.parse
from enum import Enum
from typing import Optional, Dict, Any, List

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
ALFA_EMAIL = (os.getenv("ALFA_EMAIL") or "").strip()
ALFA_API_KEY = (os.getenv("ALFA_API_KEY") or "").strip()

# можно задавать как "supersport_krsk" или "@supersport_krsk"
COORDINATOR_USERNAME = (os.getenv("COORDINATOR_USERNAME") or "").strip()
if not COORDINATOR_USERNAME:
    raise RuntimeError("ALFA_BASE is not set!")

ALFA_BASE = (os.getenv("ALFA_BASE") or "").strip().rstrip("/")
if not ALFA_BASE:
    raise RuntimeError("ALFA_BASE is not set!")

LOGIN_URL = f"{ALFA_BASE}/v2api/auth/login"
CUSTOMER_INDEX_URL = f"{ALFA_BASE}/v2api/3/customer/index"

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
if not ALFA_EMAIL or not ALFA_API_KEY:
    raise RuntimeError("ALFA_EMAIL / ALFA_API_KEY is not set")

# ----- UI -----
BTN_SWIMMING = "swimming"
BTN_RUNNING = "running"
BTN_TRIATHLON = "triathlon"
BTN_BACK = "Назад"

BTN_ASK_COORDINATOR = "Задать вопрос координатору"
BTN_LESSON_REMAINDER = "Остаток занятий"

def kb_root() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SWIMMING)],
            [KeyboardButton(text=BTN_RUNNING)],
            [KeyboardButton(text=BTN_TRIATHLON)],
        ],
        resize_keyboard=True,
    )

def kb_section() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_ASK_COORDINATOR)],
            [KeyboardButton(text=BTN_LESSON_REMAINDER)],
            [KeyboardButton(text=BTN_BACK)],
        ],
        resize_keyboard=True,
    )

class Screen(str, Enum):
    ROOT = "root"
    SWIMMING = "swimming"
    RUNNING = "running"
    TRIATHLON = "triathlon"

HELLO_BY_SCREEN: Dict[Screen, str] = {
    Screen.SWIMMING: "💙 Привет!",
    Screen.RUNNING: "💚 Привет!",
    Screen.TRIATHLON: "💜 Привет!",
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
    def __init__(self, email: str, api_key: str):
        self.email = email
        self.api_key = api_key
        self.token: Optional[str] = None
        self.token_ts: float = 0.0
        self.lock = asyncio.Lock()

    async def login(self, client: httpx.AsyncClient) -> str:
        payload = {"email": self.email, "api_key": self.api_key}
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

            if r.status_code in (401, 403):
                async with self.lock:
                    self.token = None
                    self.token_ts = 0.0
                token = await self.get_token(client)
                headers["X-ALFACRM-TOKEN"] = token
                r = await client.post(CUSTOMER_INDEX_URL, json=payload, headers=headers, timeout=20)

            if r.status_code != 200:
                raise RuntimeError(f"customerindex failed HTTP {r.status_code}: {r.text}")

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
    # TG deep-link: открывает чат с юзером и подставляет текст в поле ввода
    # (не отправляет автоматически)
    return f"https://t.me/{COORDINATOR_USERNAME}?text={urllib.parse.quote(start_text)}"

async def main():
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    alfa = AlfaCRMClient(ALFA_EMAIL, ALFA_API_KEY)

    screen_by_user: Dict[int, Screen] = {}
    waiting_phone: set[int] = set()

    def set_screen(uid: int, screen: Screen):
        screen_by_user[uid] = screen
        # если вышли из раздела — сбрасываем ожидание телефона
        if screen == Screen.ROOT:
            waiting_phone.discard(uid)

    def get_screen(uid: int) -> Screen:
        return screen_by_user.get(uid, Screen.ROOT)

    @dp.message(CommandStart())
    async def start(m: Message):
        set_screen(m.from_user.id, Screen.ROOT)
        await m.answer("Выберите раздел:", reply_markup=kb_root())

    @dp.message(F.text == BTN_SWIMMING)
    async def open_swimming(m: Message):
        set_screen(m.from_user.id, Screen.SWIMMING)
        await m.answer("Раздел swimming:", reply_markup=kb_section())

    @dp.message(F.text == BTN_RUNNING)
    async def open_running(m: Message):
        set_screen(m.from_user.id, Screen.RUNNING)
        await m.answer("Раздел running:", reply_markup=kb_section())

    @dp.message(F.text == BTN_TRIATHLON)
    async def open_triathlon(m: Message):
        set_screen(m.from_user.id, Screen.TRIATHLON)
        await m.answer("Раздел triathlon:", reply_markup=kb_section())

    @dp.message(F.text == BTN_BACK)
    async def back(m: Message):
        set_screen(m.from_user.id, Screen.ROOT)
        await m.answer("Выберите раздел:", reply_markup=kb_root())

    # ---- Задать вопрос координатору ----
    @dp.message(F.text == BTN_ASK_COORDINATOR)
    async def ask_coordinator(m: Message):
        scr = get_screen(m.from_user.id)
        if scr == Screen.ROOT:
            await m.answer("Сначала выберите раздел.", reply_markup=kb_root())
            return

        hello = HELLO_BY_SCREEN.get(scr, "Привет!")
        link = coordinator_link(hello)
        await m.answer(
            f"Откройте чат с координатором: @{COORDINATOR_USERNAME}\n"
            f"Или нажмите ссылку (текст уже подставится):\n{link}",
            reply_markup=kb_section(),
        )

    # ---- Остаток занятий ----
    @dp.message(F.text == BTN_LESSON_REMAINDER)
    async def ask_phone(m: Message):
        uid = m.from_user.id
        scr = get_screen(uid)
        if scr == Screen.ROOT:
            await m.answer("Сначала выберите раздел.", reply_markup=kb_root())
            return

        waiting_phone.add(uid)
        await m.answer("Отправьте номер телефона РФ (например 79233388881 или 89233388881).")

    @dp.message(F.text)
    async def handle_text(m: Message):
        uid = m.from_user.id

        # если ждём телефон — отрабатываем текущую функциональность
        if uid in waiting_phone:
            phone = normalize_ru_phone_to_plus7(m.text or "")
            if not phone:
                await m.answer("Неверный формат. Пример: 79233388881 или 89233388881.")
                return

            waiting_phone.discard(uid)
            await m.answer(f"Ищу клиента по номеру: {phone}")

            try:
                resp = await alfa.customer_search_by_phone(phone)
                customer = extract_customer_fields(resp)
                if not customer:
                    await m.answer("Клиент не найден.", reply_markup=kb_section())
                    return

                legal_name = customer["legal_name"] or "—"
                balance = customer["balance"]
                paid_lesson_count = customer["paid_lesson_count"]

                balance_txt = str(balance) if balance is not None else "—"
                paid_txt = str(paid_lesson_count) if paid_lesson_count is not None else "—"

                await m.answer(
                    f"Клиент: {legal_name}\n"
                    f"Баланс: {balance_txt}\n"
                    f"Оплаченных уроков: {paid_txt}",
                    reply_markup=kb_section(),
                )
            except Exception as e:
                await m.answer(f"Ошибка при запросе к AlfaCRM: {e}", reply_markup=kb_section())
            return

        # иначе — мягкая подсказка
        scr = get_screen(uid)
        if scr == Screen.ROOT:
            await m.answer("Выберите раздел:", reply_markup=kb_root())
        else:
            await m.answer("Выберите действие:", reply_markup=kb_section())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())