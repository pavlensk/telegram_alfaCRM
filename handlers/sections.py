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


def setup_sections_handlers(dp: Dispatcher, menu_msg_id_by_user: Dict[int, int]):
    INFO_CALLBACKS = {"sw:cert", "sw:prep", "sw:take"}

    @dp.callback_query(F.data.in_(INFO_CALLBACKS))
    async def info_handler(cq: CallbackQuery):
        await cq.answer()
        text_key = f"sw_{cq.data.split(':')[1]}"  # sw_cert, sw_prep, sw_take
        text = config.TEXTS[text_key]

        await menu_manager.edit_menu_message(
            cq, menu_msg_id_by_user, text,
            keyboards.kb_section_inline(config.Section.SWIMMING),
            parse_mode="HTML"
        )