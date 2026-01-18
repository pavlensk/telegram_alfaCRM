"""
HTTP-сервер на aiohttp для health checks.
"""

import asyncio
import logging

from aiohttp import web

import config

logger = logging.getLogger(__name__)

# ---- HTTP server ----

async def handle_root(request: web.Request) -> web.Response:
    """Обработчик GET / для health check."""
    return web.Response(text="Sports Bot OK\n")


async def start_web_app() -> None:
    """Запускает HTTP-сервер на aiohttp."""
    app = web.Application()
    app.add_routes([web.get("/", handle_root)])
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    
    logger.info(f"✅ Web server listening on port {config.PORT}")
    
    while True:
        await asyncio.sleep(3600)
