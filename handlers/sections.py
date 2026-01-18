"""
Хендлеры информационных разделов (сертификация, подготовка, тренировки).
"""

import logging

from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery

import config

logger = logging.getLogger(__name__)


def setup_sections_handlers(dp: Dispatcher):
    """Регистрирует хендлеры информационных разделов."""
    
    # ---- Swimming section handlers ----
    
    @dp.callback_query(F.data == "sw:cert")
    async def sw_cert(cq: CallbackQuery):
        """Информация о сертификации."""
        await cq.answer()
        
        await cq.message.answer(
            config.TEXTS["sw_cert"],
            parse_mode="HTML"
        )
    
    @dp.callback_query(F.data == "sw:prep")
    async def sw_prep(cq: CallbackQuery):
        """Информация о подготовке."""
        await cq.answer()
        
        await cq.message.answer(config.TEXTS["sw_prep"])
    
    @dp.callback_query(F.data == "sw:take")
    async def sw_take(cq: CallbackQuery):
        """Информация о тренировках."""
        await cq.answer()
        
        await cq.message.answer(
            config.TEXTS["sw_take"],
            parse_mode="HTML"
        )
