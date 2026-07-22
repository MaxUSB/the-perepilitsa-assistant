from __future__ import annotations

from dataclasses import dataclass

from aiogram import Router

from src.logic.app.context import ApplicationContext
from src.logic.modules.base import BotModule


@dataclass(slots=True)
class ModuleRegistry:
    modules: tuple[BotModule, ...]
    context: ApplicationContext

    def routers(self) -> tuple[Router, ...]:
        return tuple(module.router() for module in self.modules)

    async def startup(self) -> None:
        for module in self.modules:
            await module.startup()

    async def shutdown(self) -> None:
        for module in self.modules:
            await module.shutdown()
