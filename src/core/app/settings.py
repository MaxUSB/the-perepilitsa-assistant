from collections.abc import Callable
from typing import cast

from pydantic_settings import BaseSettings


def load_settings[SettingsT: BaseSettings](settings_type: type[SettingsT]) -> SettingsT:
    settings_factory = cast(Callable[[], SettingsT], settings_type)
    return settings_factory()
