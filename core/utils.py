"""
Утилиты для преобразования данных и парсинга.
"""

import re
import urllib.parse
from typing import Optional

import config


# ---- Utility functions ----

def normalize_ru_phone_to_plus7(text: str) -> Optional[str]:
    """Нормализует российский номер в формат 7XXXXXXXXXX."""
    digits = re.sub(r"\D", "", text or "")
    
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    
    if len(digits) == 10 and digits.startswith("9"):
        digits = "7" + digits
    
    if len(digits) == 11 and digits.startswith("7"):
        return digits
    
    return None


def coordinator_link(start_text: str) -> str:
    """Создаёт ссылку на координатора с текстом."""
    return (
        f"https://t.me/{config.COORDINATOR_USERNAME}"
        f"?text={urllib.parse.quote(start_text)}"
    )


def parse_section(raw: str) -> config.Section:
    """Парсит секцию из callback_data."""
    return config.Section(raw)


def title_root() -> str:
    """Заголовок главного меню."""
    return "Выберите направление:"


def title_section(section: config.Section) -> str:
    """Заголовок меню секции."""
    title = config.SECTION_TITLES.get(section, section.value)
    return f"{title}. Выберите действие:"
