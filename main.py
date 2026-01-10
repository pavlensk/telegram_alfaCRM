import os
import re
import time
import asyncio
from typing import Optional, Dict, Any, List

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALFA_EMAIL = os.getenv("ALFA_EMAIL", "").strip()
ALFA_API_KEY = os.getenv("ALFA_API_KEY", "").strip()

ALFA_BASE = "https://ilovesupersport.s20.online"
LOGIN_URL = f"{ALFA_BASE}/v2api/auth/login"
CUSTOMER_INDEX_URL = f"{ALFA_BASE}/v2api/3/customer/index"

if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
if not ALFA_EMAIL or not ALFA_API_KEY:
    raise RuntimeError("ALFA_EMAIL / ALFA_API_KEY is not set")

BTN_SEARCH_PHONE = "Поиск по номеру телефона"

def normalize_ru_phone_to_plus7(text: str) -> Optional[str]:
    """
    Returns phone in format +7XXXXXXXXXX
    Accepts: +7 999..., 8(999)..., 7999..., 999...
    """
    digits = re.sub(r"\D+", "", text)

    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits

    if len(digits) != 11 or not digits.startswith("7"):
        return None

    return "+" + digits

class AlfaCRMClient:
    def __init__(self, email: str, api_key: str):
        self.email = email
        self.api_key = api_key
        self._token: Optional[str] = None
        self._token_ts: float = 0.0
        self._lock = asyncio.Lock()

    async def _login(self, client: httpx.AsyncClient) -> str:
        payload = {"email": self.email, "api_key": self.api_key}
        headers = {"Accept": "application/json", "Content-Type": "application/json"}

        r = await client.post(LOGIN_URL, json=payload, headers=headers, timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f"Login failed: HTTP {r.status_code} {r.text}")

        data = r.json()
        token = data.get("token")
        if not token:
            raise RuntimeError(f"Login response has no token: {data}")

        self._token = token
        self._token_ts = time.time()
        return token

    async def get_token(self, client: httpx.AsyncClient) -> str:
        # Простейший TTL-кэш на 12 часов (можно менять)
        async with self._lock:
            if self._token and (time.time() - self._token_ts) < 12 * 3600:
                return self._token
            return await self._login(client)

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

            # если токен протух — релогин 1 раз
            if r.status_code in (401, 403):
                async with self._lock:
                    self._token = None
                    self._token_ts = 0.0
                token = await self.get_token(client)
                headers["X-ALFACRM-TOKEN"] = token
                r = await client.post(CUSTOMER_INDEX_URL, json=payload, headers=headers, timeout=20)

            if r.status_code != 200:
                raise RuntimeError(f"customer/index failed: HTTP {r.status_code} {r.text}")

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

def kb_main() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_SEARCH_PHONE)]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

async def main():
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    alfa = AlfaCRMClient(ALFA_EMAIL, ALFA_API_KEY)

    # Простое состояние "ожидаем телефон" через флаг в памяти на пользователя
    waiting_phone = set()

    @dp.message(CommandStart())
    async def start(m: Message):
        await m.answer(
            "Выберите действие кнопкой ниже.",
            reply_markup=kb_main()
        )

    @dp.message(F.text == BTN_SEARCH_PHONE)
    async def ask_phone(m: Message):
        waiting_phone.add(m.from_user.id)
        await m.answer("Отправьте номер телефона РФ (например +79233388881 или 89233388881).")

    @dp.message(F.text)
    async def handle_text(m: Message):
        uid = m.from_user.id

        # Если пользователь не нажал кнопку — подскажем
        if uid not in waiting_phone:
            await m.answer("Нажмите кнопку «Поиск по номеру телефона».", reply_markup=kb_main())
            return

        phone = normalize_ru_phone_to_plus7(m.text or "")
        if not phone:
            await m.answer("Неверный формат. Пример: +79233388881 или 89233388881.")
            return

        waiting_phone.discard(uid)
        await m.answer(f"Ищу клиента по номеру: {phone}")

        try:
            resp = await alfa.customer_search_by_phone(phone)
            customer = extract_customer_fields(resp)
            if not customer:
                await m.answer("Клиент не найден.", reply_markup=kb_main())
                return

            legal_name = customer["legal_name"] or "—"
            balance = customer["balance"]
            paid_lesson_count = customer["paid_lesson_count"]

            # на всякий случай приводим пустые значения
            balance_txt = str(balance) if balance is not None else "—"
            paid_txt = str(paid_lesson_count) if paid_lesson_count is not None else "—"

            await m.answer(
                f"Клиент: {legal_name}\n"
                f"Баланс: {balance_txt}\n"
                f"Оплаченных уроков: {paid_txt}",
                reply_markup=kb_main()
            )

        except Exception as e:
            await m.answer(f"Ошибка при запросе к AlfaCRM: {e}", reply_markup=kb_main())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())