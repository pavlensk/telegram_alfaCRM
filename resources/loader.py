"""
Загрузчик ресурсных JSON-файлов.
Инициализирует глобальные переменные конфигурации.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any

import config

logger = logging.getLogger(__name__)

class Resources:
    """Загрузчик ресурсных JSON-файлов."""

    # ✅ ИСПРАВЛЕНО: текущая папка resources/
    RESOURCES_DIR = Path(__file__).parent

    @classmethod
    def load(cls, filename: str) -> Dict:
        """Загружает JSON ресурс из папки resources/."""
        path = cls.RESOURCES_DIR / filename

        if not path.exists():
            raise FileNotFoundError(f"Resource not found: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"✅ Loaded resource: {filename}")
            return data
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON in {filename}: {e}")

def initialize_resources():
    """Инициализирует все ресурсы при старте."""
    try:
        config.UI_LABELS = Resources.load("ui_labels.json")
        config.SECTIONS = Resources.load("sections.json")
        config.QUIZ_DATA = Resources.load("quiz_questions.json")
        config.TEXTS = Resources.load("texts.json")
        
        logger.info("✅ All resources loaded successfully")
    except (FileNotFoundError, RuntimeError) as e:
        logger.error(f"❌ Failed to load resources: {e}")
        raise
    
    # ---- Parse quiz data ----
    
    config.SWIMMING_LEVEL_QUESTIONS = config.QUIZ_DATA["questions"]
    config.QUIZ_TTL_SECONDS = config.QUIZ_DATA["quiz_ttl_seconds"]
    
    # Парсим индексы вопросов
    config.QUIZ_IDX_FORMAT = config.QUIZ_DATA["quiz_indices"]["format"]
    config.QUIZ_IDX_EXPERIENCE = config.QUIZ_DATA["quiz_indices"]["experience"]
    config.QUIZ_IDX_DISTANCE = config.QUIZ_DATA["quiz_indices"]["distance"]
    config.QUIZ_IDX_FREESTYLE = config.QUIZ_DATA["quiz_indices"]["freestyle"]
    config.QUIZ_IDX_GOAL = config.QUIZ_DATA["quiz_indices"]["goal"]
    
    # Преобразуем level_results в нужный формат
    for key_str, data in config.QUIZ_DATA["level_results"].items():
        # Парсим "(min,max)" в кортеж (min, max)
        clean_key = key_str.strip("()")
        min_score, max_score = map(int, clean_key.split(","))
        key = (min_score, max_score)
        
        config.LEVEL_RESULTS[key] = (data["title"], data["desc"])
        config.LEVEL_PATHS[key] = data["path"]
    
    # Получаем секции из ресурсов
    config.SECTION_TITLES = {
        config.Section(k): v["title"]
        for k, v in config.SECTIONS["sections"].items()
    }
    
    config.HELLO_BY_SECTION = {
        config.Section(k): v["hello"]
        for k, v in config.SECTIONS["sections"].items()
    }
