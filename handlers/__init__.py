"""
Инициализация и регистрация всех хендлеров.
"""

from aiogram import Dispatcher

from . import navigation, customer, quiz, sections


def setup_all_handlers(
    dp: Dispatcher,
    menu_msg_id_by_user: dict,
    waiting_phone_section_by_user: dict,
    quiz_state: dict,
    alfa
):
    """Регистрирует все хендлеры в диспетчере."""
    
    # Регистрируем хендлеры навигации
    navigation.setup_navigation_handlers(
        dp,
        menu_msg_id_by_user,
        waiting_phone_section_by_user
    )
    
    # Регистрируем хендлеры поиска клиентов
    customer.setup_customer_handlers(
        dp,
        menu_msg_id_by_user,
        waiting_phone_section_by_user,
        alfa
    )
    
    # Регистрируем хендлеры квиза
    quiz.setup_quiz_handlers(
        dp,
        menu_msg_id_by_user,
        quiz_state
    )
    
    # Регистрируем хендлеры информационных разделов
    sections.setup_sections_handlers(dp)
