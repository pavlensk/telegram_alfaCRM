"""
Асинхронный клиент для интеграции с AlfaCRM.
"""

import time
import asyncio
import logging
from typing import Dict, Any, Optional

import httpx

import config

logger = logging.getLogger(__name__)

# ---- AlfaCRM client ----

class AlfaCRMClient:
    """Асинхронный HTTP-клиент для AlfaCRM API с управлением токенами."""
    
    def __init__(self, email: str, apikey: str):
        self.email = email
        self.apikey = apikey
        self.token: Optional[str] = None
        self.token_ts: float = 0.0
        self.lock = asyncio.Lock()
    
    async def login(self, client: httpx.AsyncClient) -> str:
        """Получает новый токен через логин."""
        payload = {"email": self.email, "api_key": self.apikey}
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        
        r = await client.post(config.LOGIN_URL, json=payload, headers=headers, timeout=20)
        
        if r.status_code != 200:
            raise RuntimeError(f"Login failed HTTP {r.status_code}: {r.text}")
        
        data = r.json()
        token = data.get("token")
        
        if not token:
            raise RuntimeError(f"Login response has no token: {data}")
        
        self.token = token
        self.token_ts = time.time()
        
        return token
    
    async def get_token(self, client: httpx.AsyncClient) -> str:
        """Возвращает кэшированный токен или получает новый."""
        async with self.lock:
            if self.token and (time.time() - self.token_ts) < 12 * 3600:
                return self.token
            
            return await self.login(client)
    
    async def customer_search_by_phone(self, phone_plus7: str) -> Dict[str, Any]:
        """Поиск клиента по телефону в формате 7XXXXXXXXXX."""
        async with httpx.AsyncClient() as client:
            token = await self.get_token(client)
            
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-ALFACRM-TOKEN": token,
            }
            
            payload = {"phone": phone_plus7}
            
            r = await client.post(
                config.CUSTOMER_INDEX_URL,
                json=payload,
                headers=headers,
                timeout=20,
            )
            
            if r.status_code in (401, 403):
                async with self.lock:
                    self.token = None
                    self.token_ts = 0.0
                
                token = await self.get_token(client)
                headers["X-ALFACRM-TOKEN"] = token
                
                r = await client.post(
                    config.CUSTOMER_INDEX_URL,
                    json=payload,
                    headers=headers,
                    timeout=20,
                )
            
            if r.status_code != 200:
                raise RuntimeError(
                    f"customer/index failed HTTP {r.status_code}: {r.text}"
                )
            
            return r.json()


def extract_customer_fields(resp: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Извлекает поля клиента из ответа AlfaCRM."""
    items: list = resp.get("items") or []
    
    if not items:
        return None
    
    c = items[0] or {}
    
    return {
        "legal_name": c.get("legal_name") or "",
        "balance": c.get("balance"),
        "paid_lesson_count": c.get("paid_lesson_count"),
    }
