from src.api.telegram.common import WELCOME_MESSAGE
from src.api.telegram.fallback import FALLBACK_MESSAGE


def test_welcome_message_contains_supported_input_examples() -> None:
    assert "https://youtu.be/" in WELCOME_MESSAGE
    assert "/fuel" in WELCOME_MESSAGE
    assert "YouTube" in WELCOME_MESSAGE
    assert "АЗС" in WELCOME_MESSAGE


def test_fallback_message_contains_supported_input_examples() -> None:
    assert "https://youtu.be/" in FALLBACK_MESSAGE
    assert "/fuel" in FALLBACK_MESSAGE
    assert "YouTube" in FALLBACK_MESSAGE
    assert "АЗС" in FALLBACK_MESSAGE
