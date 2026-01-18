"""
Генераторы инлайн-клавиатур для меню и квизов.
"""

from typing import Dict, Any, Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import config
from core import utils

# ---- Inline keyboards ----

def kb_root_inline(ui_labels: Dict) -> InlineKeyboardMarkup:
    """Главное меню с выбором направления."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=ui_labels["btn_swimming"],
                    callback_data="nav:section:swimming"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=ui_labels["btn_running"],
                    callback_data="nav:section:running"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=ui_labels["btn_triathlon"],
                    callback_data="nav:section:triathlon"
                ),
            ],
        ]
    )


def kb_section_inline(section: config.Section) -> InlineKeyboardMarkup:
    """Меню конкретной секции."""
    hello = config.HELLO_BY_SECTION.get(section, "Привет! Напишите координатору.")
    link = utils.coordinator_link(hello)
    s = section.value
    
    keyboard = [
        [
            InlineKeyboardButton(
                text=config.UI_LABELS["btn_write_coordinator"],
                url=link,
            ),
        ],
        [
            InlineKeyboardButton(
                text=config.UI_LABELS["btn_lesson_remainder"],
                callback_data=f"act:lesson_remainder:{s}",
            ),
        ],
    ]
    
    if section == config.Section.SWIMMING:
        keyboard.extend([
            [
                InlineKeyboardButton(
                    text=config.UI_LABELS["btn_sw_level"],
                    callback_data="sw:level",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=config.UI_LABELS["btn_sw_cert"],
                    callback_data="sw:cert",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=config.UI_LABELS["btn_sw_prep"],
                    callback_data="sw:prep",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=config.UI_LABELS["btn_sw_take"],
                    callback_data="sw:take",
                ),
            ],
        ])
    
    keyboard.append(
        [InlineKeyboardButton(text=config.UI_LABELS["btn_back"], callback_data="nav:root")]
    )
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_question_keyboard_adaptive(
    q_data: Dict[str, Any],
    uid: int = None,
    quiz_state: Optional[Dict[int, Dict]] = None
) -> InlineKeyboardMarkup:
    """Универсальная клавиатура для вопросов квиза.
    
    Для вопроса 5 скрывает вариант "a" если score > 2.
    """
    buttons = []
    answers_keys = list(q_data["answers"].keys())
    
    # Для вопроса 5 скрываем вариант "a" если score > 2
    if q_data["question"].startswith("5️⃣") and uid and quiz_state and uid in quiz_state:
        score = quiz_state[uid]["score"]
        if score > 2:
            answers_keys = [k for k in answers_keys if k != "a"]
    
    # Динамическая нумерация А) Б) В)
    letter_map = {0: "А)", 1: "Б)", 2: "В)"}
    
    for idx, key in enumerate(answers_keys):
        text = q_data["answers"][key][0]
        buttons.append([InlineKeyboardButton(
            text=f"{letter_map[idx]} {text}",
            callback_data=f"quiz:answer:{key}"
        )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
