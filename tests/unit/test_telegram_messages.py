from src.api.telegram.common import WELCOME_MESSAGE
from src.api.telegram.fallback import FALLBACK_MESSAGE


def test_welcome_message_contains_supported_commands() -> None:
    assert "youtube.com" in WELCOME_MESSAGE
    assert "/fuel" in WELCOME_MESSAGE
    assert "/notify_fuel" in WELCOME_MESSAGE
    assert "YouTube" in WELCOME_MESSAGE
    assert "GPN" in WELCOME_MESSAGE


def test_fallback_message_reports_unrecognized_input() -> None:
    assert "Не удалось распознать сообщение" in FALLBACK_MESSAGE
