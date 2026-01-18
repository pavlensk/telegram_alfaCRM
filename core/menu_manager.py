"""
Управление меню-сообщениями в чате.
Гарантирует одно меню-сообщение на пользователя.
"""

from typing import Dict

from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup


# ---- Menu management ----

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
    """Редактирует меню-сообщение при обработке CallbackQuery.
    
    Если есть сохранённый message_id → редактирует его.
    Иначе пытается отредактировать текущее сообщение.
    Если не получится → отправляет новое и сохраняет ID.
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
