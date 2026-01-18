"""
Хендлеры поиска клиентов по номеру телефона.
"""

import logging
from typing import Dict

from aiogram import Dispatcher, F
from aiogram.types import Message, CallbackQuery

import config
from core import keyboards, menu_manager, utils
from core.crm_client import extract_customer_fields

logger = logging.getLogger(__name__)


def setup_customer_handlers(
    dp: Dispatcher,
    menu_msg_id_by_user: Dict[int, int],
    waiting_phone_section_by_user: Dict[int, config.Section],
    alfa
):
    """Регистрирует хендлеры поиска клиентов."""
    
    @dp.callback_query(F.data.startswith("act:lesson_remainder:"))
    async def act_lesson_remainder(cq: CallbackQuery):
        """Инициирует поиск клиента по номеру телефона."""
        raw = (cq.data or "").split(":")[-1]
        section = utils.parse_section(raw)
        
        waiting_phone_section_by_user[cq.from_user.id] = section
        
        await menu_manager.edit_menu_message(
            cq,
            menu_msg_id_by_user,
            config.TEXTS["invalid_phone"],
            keyboards.kb_section_inline(section),
        )
    
    @dp.message(F.text)
    async def handle_text(m: Message):
        """Обработчик текстовых сообщений (поиск клиента по номеру)."""
        uid = m.from_user.id
        section = waiting_phone_section_by_user.get(uid)
        
        # Если не ожидаем номер телефона → показываем главное меню
        if section is None:
            await menu_manager.ensure_menu_message(
                m,
                menu_msg_id_by_user,
                utils.title_root(),
                keyboards.kb_root_inline(config.UI_LABELS),
            )
            return
        
        # Нормализуем номер телефона
        phone = utils.normalize_ru_phone_to_plus7(m.text or "")
        
        if not phone:
            await m.answer(config.TEXTS["invalid_phone"])
            return
        
        waiting_phone_section_by_user.pop(uid, None)
        
        # Показываем, что ищем
        await menu_manager.ensure_menu_message(
            m,
            menu_msg_id_by_user,
            text=f"🔍 Ищу клиента по номеру: +{phone}",
            markup=keyboards.kb_section_inline(section),
        )
        
        # Ищем клиента в AlfaCRM
        try:
            resp = await alfa.customer_search_by_phone(phone)
            customer = extract_customer_fields(resp)
            
            if not customer:
                await menu_manager.ensure_menu_message(
                    m,
                    menu_msg_id_by_user,
                    config.TEXTS["client_not_found"],
                    keyboards.kb_section_inline(section),
                )
                return
            
            legal_name = customer.get("legal_name") or "—"
            balance_txt = (
                str(customer.get("balance"))
                if customer.get("balance") is not None
                else "—"
            )
            payed_txt = (
                str(customer.get("paid_lesson_count"))
                if customer.get("paid_lesson_count") is not None
                else "—"
            )
            
            await menu_manager.ensure_menu_message(
                m,
                menu_msg_id_by_user,
                text=(
                    f"👤 Клиент: {legal_name}\n"
                    f"💰 Баланс: {balance_txt}\n"
                    f"📚 Оплаченных уроков: {payed_txt}"
                ),
                markup=keyboards.kb_section_inline(section),
            )
        
        except Exception as e:
            logger.error(
                f"❌ AlfaCRM search failed for phone {phone}: "
                f"{type(e).__name__}: {e}"
            )
            
            await menu_manager.ensure_menu_message(
                m,
                menu_msg_id_by_user,
                config.TEXTS["service_unavailable"],
                keyboards.kb_section_inline(section),
            )
