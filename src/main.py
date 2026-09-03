import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode

from src.core.app import AppConfig, load_settings
from src.core.bot.config import BotConfig
from src.core.gpn import GpnConfig
from src.core.youtube import YoutubeConfig
from src.logic.app.context import ApplicationContext
from src.logic.app.factory import create_dispatcher, create_module_registry


def configure_logging(app_config: AppConfig) -> None:
    logging.basicConfig(
        level=getattr(logging, app_config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def run() -> None:
    app_config = load_settings(AppConfig)
    bot_config = load_settings(BotConfig)
    youtube_config = load_settings(YoutubeConfig)
    gpn_config = load_settings(GpnConfig)

    configure_logging(app_config)

    context = ApplicationContext.from_configs(
        app_config=app_config,
        bot_config=bot_config,
        youtube_config=youtube_config,
        gpn_config=gpn_config,
    )
    api_server = (
        TelegramAPIServer.from_base(bot_config.telegram_api_base_url, is_local=True)
        if bot_config.telegram_api_base_url is not None
        else None
    )
    bot_session = (
        AiohttpSession(proxy=bot_config.telegram_proxy_url, api=api_server)
        if api_server is not None
        else AiohttpSession(proxy=bot_config.telegram_proxy_url)
    )

    bot = Bot(
        token=bot_config.token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=bot_session,
    )

    module_registry = create_module_registry(context=context, bot=bot)
    dispatcher = create_dispatcher(context=context, module_registry=module_registry)

    logging.getLogger(__name__).info("Bot polling started")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await module_registry.startup()
        await dispatcher.start_polling(bot)
    finally:
        try:
            await module_registry.shutdown()
        finally:
            await bot.session.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
