from typing import Any

from aiogram.filters import BaseFilter
from aiogram.types import Message

from src.core.youtube.utils import extract_youtube_url


class YoutubeUrlFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool | dict[str, Any]:
        text = message.text
        if text is None:
            return False

        youtube_url = extract_youtube_url(text)
        if youtube_url is None:
            return False

        return {"youtube_url": youtube_url}
