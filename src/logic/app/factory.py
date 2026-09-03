from aiogram import Bot, Dispatcher

from src.api.telegram.common import create_common_router
from src.api.telegram.fallback import create_fallback_router
from src.logic.app.context import ApplicationContext
from src.logic.bot.access import AllowedUserMiddleware
from src.logic.gpn.module import GpnModule
from src.logic.modules.registry import ModuleRegistry
from src.logic.youtube.module import YoutubeModule


def create_module_registry(*, context: ApplicationContext, bot: Bot) -> ModuleRegistry:
    return ModuleRegistry(
        modules=(
            YoutubeModule(),
            GpnModule(bot=bot, config=context.gpn_config, service=context.gpn_service),
        )
    )


def create_dispatcher(*, context: ApplicationContext, module_registry: ModuleRegistry) -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.update.outer_middleware(AllowedUserMiddleware(context.bot_config.allowed_user_ids))
    dispatcher["youtube_service"] = context.youtube_service
    dispatcher["gpn_service"] = context.gpn_service

    dispatcher.include_router(create_common_router())
    for router in module_registry.routers():
        dispatcher.include_router(router)
    dispatcher.include_router(create_fallback_router())

    return dispatcher
