"""
Хендлеры навигации по меню.
"""

import logging
from typing import Dict

from aiogram import Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

import config
import keyboards
import menu_manager
import utils

logger = logging.getLogger(__name__)


def setup_navigation_handlers(
    dp: Dispatcher,
    menu_msg_id_by_user: Dict[int, int],
    waiting_phone_section_by_user: Dict[int, config.Section]
):
    """Регистрирует хендлеры навигации."""
    
    # ---- Main navigation handlers ----
    
    @dp.message(CommandStart())
    async def start(m: Message):
        """Обработчик /start команды."""
        waiting_phone_section_by_user.pop(m.from_user.id, None)
        
        await menu_manager.ensure_menu_message(
            m,
            menu_msg_id_by_user,
            utils.title_root(),
            keyboards.kb_root_inline(config.UI_LABELS),
        )
    
    @dp.callback_query(F.data == "nav:root")
    async def nav_root(cq: CallbackQuery):
        """Возврат в главное меню."""
        waiting_phone_section_by_user.pop(cq.from_user.id, None)
        
        await menu_manager.edit_menu_message(
            cq,
            menu_msg_id_by_user,
            utils.title_root(),
            keyboards.kb_root_inline(config.UI_LABELS),
        )
    
    @dp.callback_query(F.data.startswith("nav:section:"))
    async def nav_section(cq: CallbackQuery):
        """Переход в меню конкретной секции."""
        waiting_phone_section_by_user.pop(cq.from_user.id, None)
        
        raw = (cq.data or "").split(":")[-1]
        section = utils.parse_section(raw)
        
        await menu_manager.edit_menu_message(
            cq,
            menu_msg_id_by_user,
            utils.title_section(section),
            keyboards.kb_section_inline(section),
        )
