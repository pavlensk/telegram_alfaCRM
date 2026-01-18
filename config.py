"""
Конфигурация приложения.
Загружает переменные окружения и определяет глобальные константы.
"""

import os
from enum import Enum
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

# ---- Environment variables ----

BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
ALFA_EMAIL = (os.getenv("ALFA_EMAIL") or "").strip()
ALFA_API_KEY = (os.getenv("ALFA_API_KEY") or "").strip()
COORDINATOR_USERNAME = (os.getenv("COORDINATOR_USERNAME") or "").strip()
ALFA_BASE = (os.getenv("ALFA_BASE") or "").strip().rstrip("/")
PORT = int(os.getenv("PORT", "8000"))
BOT_STATUS_CHAT_ID = int(os.getenv("BOT_STATUS_CHAT_ID", "0"))
SWIMMING_BASE_URL = (os.getenv("SWIMMING_BASE_URL") or "").strip()

LOGIN_URL = f"{ALFA_BASE}/v2api/auth/login"
CUSTOMER_INDEX_URL = f"{ALFA_BASE}/v2api/3/customer/index"

REQUIRED_ENVS = [
    ("COORDINATOR_USERNAME", COORDINATOR_USERNAME),
    ("ALFA_BASE", ALFA_BASE),
    ("TELEGRAM_BOT_TOKEN", BOT_TOKEN),
    ("ALFA_EMAIL", ALFA_EMAIL),
    ("ALFA_API_KEY", ALFA_API_KEY),
    ("SWIMMING_BASE_URL", SWIMMING_BASE_URL),
]

for env_name, value in REQUIRED_ENVS:
    if not value:
        raise RuntimeError(f"{env_name} is not set")

# ---- Section enum ----

class Section(str, Enum):
    """Секции/направления спорта."""
    SWIMMING = "swimming"
    RUNNING = "running"
    TRIATHLON = "triathlon"


# ---- Global resources (заполняются в resources_loader.initialize_resources) ----

UI_LABELS: Dict[str, Any] = {}
SECTIONS: Dict[str, Any] = {}
QUIZ_DATA: Dict[str, Any] = {}
TEXTS: Dict[str, Any] = {}
LEVEL_RESULTS: Dict[tuple, tuple] = {}
LEVEL_PATHS: Dict[tuple, str] = {}
SECTION_TITLES: Dict[Section, str] = {}
HELLO_BY_SECTION: Dict[Section, str] = {}

# ---- Parse quiz data (заполняется в resources_loader) ----

SWIMMING_LEVEL_QUESTIONS = []
QUIZ_TTL_SECONDS = 600

QUIZ_IDX_FORMAT = 0
QUIZ_IDX_EXPERIENCE = 1
QUIZ_IDX_DISTANCE = 2
QUIZ_IDX_FREESTYLE = 3
QUIZ_IDX_GOAL = 4
