"""
Управление меню-сообщениями в чате.
Гарантирует одно меню-сообщение на пользователя.
"""

import logging
from typing import Dict

from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


async def ensure_menu_message(
    m: Message,
    menu_msg_id_by_user: Dict[int, int],
    text: str,
    markup: InlineKeyboardMarkup,
) -> None:
    """Гарантирует одно меню-сообщение при обработке Message.
    
    Если есть сохранённый message_id → редактирует его.
    Иначе → отправляет новое и сохраняет ID.
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
                parse_mode="HTML", 
            )
            logger.info(f"✅ ensure: edited msg_id={msg_id} for uid={uid}")
            return
        except Exception as e:
            logger.warning(f"⚠️ ensure: edit failed uid={uid}: {e}")

    sent = await m.answer(text, reply_markup=markup, parse_mode="HTML") 
    menu_msg_id_by_user[uid] = sent.message_id
    logger.info(f"✅ ensure: new msg_id={sent.message_id} for uid={uid}")


async def edit_menu_message(
    cq: CallbackQuery,
    menu_msg_id_by_user: Dict[int, int],
    text: str,
    markup: InlineKeyboardMarkup,
    parse_mode: str = "HTML", 
) -> None:
    """Редактирует меню-сообщение при обработке CallbackQuery.
    
    Если есть сохранённый message_id → редактирует его.
    Иначе пытается отредактировать текущее сообщение.
    Если не получится → отправляет новое и сохраняет ID.
    """
    uid = cq.from_user.id
    await cq.answer()

    msg_id = menu_msg_id_by_user.get(uid)
    logger.info(f"🔍 edit uid={uid} saved_msg_id={msg_id} cq_msg_id={cq.message.message_id}")

    if msg_id:
        try:
            await cq.bot.edit_message_text(
                chat_id=cq.message.chat.id,
                message_id=msg_id,
                text=text,
                reply_markup=markup,
                parse_mode=parse_mode,  # ✅
            )
            logger.info(f"✅ edit: edited msg_id={msg_id} uid={uid}")
            return
        except Exception as e:  # ✅ as e!
            logger.error(f"❌ edit failed uid={uid} msg_id={msg_id}: {e}")

    # Fallback 1: текущее сообщение
    try:
        await cq.message.edit_text(text, reply_markup=markup, parse_mode=parse_mode)  # ✅
        menu_msg_id_by_user[uid] = cq.message.message_id
        logger.info(f"✅ edit: fallback edit uid={uid}")
        return
    except Exception as e:
        logger.warning(f"⚠️ fallback edit failed uid={uid}: {e}")

    # Fallback 2: новое сообщение
    sent = await cq.message.answer(text, reply_markup=markup, parse_mode=parse_mode)  # ✅
    menu_msg_id_by_user[uid] = sent.message_id
    logger.info(f"✅ edit: new msg_id={sent.message_id} uid={uid}")
