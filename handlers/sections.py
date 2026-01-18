"""
Хендлеры информационных разделов (сертификация, подготовка, тренировки).
"""

import logging
from typing import Dict

from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery

import config
from core import menu_manager, keyboards

logger = logging.getLogger(__name__)


def setup_sections_handlers(
    dp: Dispatcher,
    menu_msg_id_by_user: Dict[int, int],
):
    """Регистрирует хендлеры информационных разделов."""

    @dp.callback_query(F.data == "sw:cert")
    async def sw_cert(cq: CallbackQuery):
        """Справка по плаванию."""
        await cq.answer()
        await menu_manager.edit_menu_message(
            cq,
            menu_msg_id_by_user,
            config.TEXTS["sw_cert"],
            keyboards.kb_section_inline(config.Section.SWIMMING),
        )

    @dp.callback_query(F.data == "sw:prep")
    async def sw_prep(cq: CallbackQuery):
        """Подготовка к заплыву."""
        await cq.answer()
        await menu_manager.edit_menu_message(
            cq,
            menu_msg_id_by_user,
            config.TEXTS["sw_prep"],
            keyboards.kb_section_inline(config.Section.SWIMMING),
        )

    @dp.callback_query(F.data == "sw:take")
    async def sw_take(cq: CallbackQuery):
        """Что взять в бассейн."""
        await cq.answer()
        await menu_manager.edit_menu_message(
            cq,
            menu_msg_id_by_user,
            config.TEXTS["sw_take"],
            keyboards.kb_section_inline(config.Section.SWIMMING),
        )