from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class YoutubeDownloadCallback(CallbackData, prefix="yt"):
    request_id: str
    option_key: str
