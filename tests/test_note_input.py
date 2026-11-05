import pytest
from tgkit import UserInputError

from services.notes_manager import MAX_BODY_LEN, MAX_TITLE_LEN, clean_body, clean_title


def test_title_and_body_are_trimmed():
    assert clean_title("  Покупки  ") == "Покупки"
    assert clean_body("\nмолоко\n") == "молоко"


@pytest.mark.parametrize("text", [None, "", "   ", "x" * (MAX_TITLE_LEN + 1)])
def test_bad_title_is_rejected(text):
    with pytest.raises(UserInputError):
        clean_title(text)


@pytest.mark.parametrize("text", [None, "", "   ", "x" * (MAX_BODY_LEN + 1)])
def test_bad_body_is_rejected(text):
    """None — стикер или голосовое вместо текста."""
    with pytest.raises(UserInputError):
        clean_body(text)
