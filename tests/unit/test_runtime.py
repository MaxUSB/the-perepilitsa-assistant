import asyncio
from unittest.mock import AsyncMock

from aiogram.types import TelegramObject, User

from src.logic.bot.access import AllowedUserMiddleware
from src.logic.modules.registry import ModuleRegistry
from src.logic.youtube.module import YoutubeModule


async def test_access_middleware_allows_only_configured_users() -> None:
    middleware = AllowedUserMiddleware(frozenset({1}))
    handler = AsyncMock(return_value="handled")
    event = AsyncMock(spec=TelegramObject)

    allowed_result = await middleware(handler, event, {"event_from_user": User(id=1, is_bot=False, first_name="A")})
    denied_result = await middleware(handler, event, {"event_from_user": User(id=2, is_bot=False, first_name="B")})
    userless_result = await middleware(handler, event, {})

    assert allowed_result == "handled"
    assert denied_result is None
    assert userless_result is None
    handler.assert_awaited_once()


async def test_module_registry_shuts_modules_down_in_reverse_order() -> None:
    calls: list[str] = []
    first = AsyncMock()
    second = AsyncMock()
    first.router.return_value = AsyncMock()
    second.router.return_value = AsyncMock()
    first.shutdown.side_effect = lambda: calls.append("first")
    second.shutdown.side_effect = lambda: calls.append("second")
    registry = ModuleRegistry(modules=(first, second))

    await registry.shutdown()

    assert calls == ["second", "first"]


async def test_youtube_module_cancels_background_tasks_on_shutdown() -> None:
    module = YoutubeModule()
    task_started = asyncio.Event()

    async def background_job() -> None:
        task_started.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(background_job())
    module._background_tasks.add(task)
    await task_started.wait()

    await module.shutdown()

    assert task.cancelled()
    assert not module._background_tasks
