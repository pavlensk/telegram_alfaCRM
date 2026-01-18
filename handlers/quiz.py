"""
Хендлеры для квиза определения уровня плавания.
"""

import logging
from typing import Dict

from aiogram import Dispatcher, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import config
import keyboards
import menu_manager
import utils

logger = logging.getLogger(__name__)


def setup_quiz_handlers(
    dp: Dispatcher,
    menu_msg_id_by_user: Dict[int, int],
    quiz_state: Dict[int, Dict]
):
    """Регистрирует хендлеры квиза."""
    
    def validate_quiz_state(uid: int) -> bool:
        """Проверяет валидность quiz_state с TTL."""
        if uid not in quiz_state:
            return False
        
        import time
        if time.time() - quiz_state[uid]["timestamp"] > config.QUIZ_TTL_SECONDS:
            quiz_state.pop(uid, None)
            return False
        
        return True
    
    def adaptive_next_question(uid: int, current_q_idx: int, current_answer: str) -> int:
        """Возвращает индекс следующего вопроса или len() для завершения."""
        state = quiz_state[uid]
        q_data = config.SWIMMING_LEVEL_QUESTIONS[current_q_idx]
        
        if current_answer not in q_data["answers"]:
            logger.error(f"❌ Invalid answer '{current_answer}' for question {current_q_idx}")
            return len(config.SWIMMING_LEVEL_QUESTIONS)
        
        score = q_data["answers"][current_answer][1]
        state["score"] += score
        
        # Адаптивная логика переходов
        if current_q_idx == config.QUIZ_IDX_FORMAT:
            if current_answer == "b":  # Персональные
                return len(config.SWIMMING_LEVEL_QUESTIONS)
        
        elif current_q_idx == config.QUIZ_IDX_EXPERIENCE:
            if current_answer in ("a", "c"):
                return config.QUIZ_IDX_FREESTYLE  # Пропускаем расстояние
        
        elif current_q_idx == config.QUIZ_IDX_DISTANCE:
            if current_answer == "a":
                return config.QUIZ_IDX_GOAL  # Пропускаем кроль
        
        return current_q_idx + 1
    
    async def show_quiz_result(cq: CallbackQuery, uid: int) -> None:
        """Показывает результат квиза."""
        total_score = quiz_state[uid]["score"]
        
        level_title = "🌊 Level 0"
        level_desc = "Неизвестный уровень"
        level_url = config.SWIMMING_BASE_URL
        
        # Ищем соответствующий уровень
        for (min_s, max_s), (title, desc) in config.LEVEL_RESULTS.items():
            if min_s <= total_score <= max_s:
                level_title = title
                level_desc = desc
                
                if min_s != -1:
                    level_path = config.LEVEL_PATHS.get((min_s, max_s), "")
                    level_url = f"{config.SWIMMING_BASE_URL}{level_path}"
                
                break
        
        result_text = (
            f"🏊 <b>Результат вашего теста:</b>\n\n"
            f"<b>{level_title}</b>\n\n"
            f"{level_desc}"
        )
        
        if total_score != -1:
            result_text += f"\n\n📊 <b>Баллы:</b> {total_score}/8"
        
        result_text += "\n\n💬 Готовы начать? Напишите координатору!"
        
        hello = config.HELLO_BY_SECTION[config.Section.SWIMMING]
        coordinator_url = utils.coordinator_link(
            f"{hello} Интересует {level_title}"
        )
        
        buttons = [
            [InlineKeyboardButton(
                text="📖 Подробнее о программе",
                url=level_url
            )],
            [InlineKeyboardButton(
                text="💬 Написать координатору",
                url=coordinator_url
            )],
        ]
        
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await cq.message.answer(result_text, reply_markup=markup, parse_mode="HTML")
    
    # ---- Swimming level quiz handlers ----
    
    @dp.callback_query(F.data == "sw:level")
    async def sw_level_start(cq: CallbackQuery):
        """Начинает квиз определения уровня плавания."""
        import time
        
        uid = cq.from_user.id
        await cq.answer()
        
        # Инициализируем состояние квиза
        quiz_state[uid] = {
            "question_idx": config.QUIZ_IDX_FORMAT,
            "score": 0,
            "timestamp": time.time(),
        }
        
        q_data = config.SWIMMING_LEVEL_QUESTIONS[config.QUIZ_IDX_FORMAT]
        
        await cq.message.answer(
            q_data["question"],
            reply_markup=keyboards.get_question_keyboard_adaptive(q_data, uid, quiz_state)
        )
    
    @dp.callback_query(F.data.startswith("quiz:answer:"))
    async def quiz_answer(cq: CallbackQuery):
        """Обработчик ответа на вопрос квиза."""
        uid = cq.from_user.id
        
        if not validate_quiz_state(uid):
            await cq.answer(config.TEXTS["quiz_expired"])
            return
        
        answer_key = cq.data.split(":")[-1]
        q_idx = quiz_state[uid]["question_idx"]
        
        await cq.answer()
        
        # Вычисляем следующий вопрос
        next_idx = adaptive_next_question(uid, q_idx, answer_key)
        quiz_state[uid]["question_idx"] = next_idx
        
        # Если квиз завершён → показываем результат
        if next_idx >= len(config.SWIMMING_LEVEL_QUESTIONS):
            await show_quiz_result(cq, uid)
            quiz_state.pop(uid, None)
        
        # Иначе показываем следующий вопрос
        else:
            next_q = config.SWIMMING_LEVEL_QUESTIONS[next_idx]
            
            await cq.message.answer(
                next_q["question"],
                reply_markup=keyboards.get_question_keyboard_adaptive(
                    next_q, uid, quiz_state
                )
            )
