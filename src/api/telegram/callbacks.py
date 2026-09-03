from aiogram.filters.callback_data import CallbackData


class YoutubeDownloadCallback(CallbackData, prefix="yt"):
    request_id: str
    option_key: str


class GpnFuelCallback(CallbackData, prefix="gpn_fuel"):
    group_key: str
