from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from src.core.app.config import AppConfig
from src.core.bot.config import BotConfig
from src.core.youtube.config import YoutubeConfig
from src.logic.app.context import ApplicationContext
from src.logic.app.factory import create_dispatcher, create_module_registry


def configure_logging(app_config: AppConfig) -> None:
    logging.basicConfig(
        level=getattr(logging, app_config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def run() -> None:
    app_config = AppConfig()
    bot_config = BotConfig()
    youtube_config = YoutubeConfig()

    configure_logging(app_config)

    context = ApplicationContext.from_configs(
        app_config=app_config,
        bot_config=bot_config,
        youtube_config=youtube_config,
    )
    module_registry = create_module_registry(context)
    dispatcher = create_dispatcher(context=context, module_registry=module_registry)
    bot_session = AiohttpSession(proxy=bot_config.telegram_proxy_url)

    bot = Bot(
        token=bot_config.token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=bot_session,
    )

    logging.getLogger(__name__).info("Bot polling started")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await module_registry.startup()
        await dispatcher.start_polling(bot)
    finally:
        await module_registry.shutdown()
        await bot.session.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
