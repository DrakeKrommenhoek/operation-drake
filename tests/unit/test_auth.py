import os

import pytest


@pytest.fixture(autouse=True)
def clear_settings():
    from operation_drake.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_is_user_allowed_when_no_restriction():
    os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
    from operation_drake.config import get_settings

    get_settings.cache_clear()
    s = get_settings()
    assert s.is_user_allowed("99999") is True
    assert s.is_user_allowed("anyone") is True


def test_is_user_allowed_with_specific_ids():
    os.environ["TELEGRAM_ALLOWED_USER_IDS"] = "111,222,333"
    from operation_drake.config import get_settings

    get_settings.cache_clear()
    s = get_settings()
    assert s.is_user_allowed("111") is True
    assert s.is_user_allowed("222") is True
    assert s.is_user_allowed("444") is False
    assert s.is_user_allowed("") is False


def test_allowed_user_ids_strips_whitespace():
    os.environ["TELEGRAM_ALLOWED_USER_IDS"] = " 111 , 222 , 333 "
    from operation_drake.config import get_settings

    get_settings.cache_clear()
    s = get_settings()
    assert "111" in s.allowed_user_ids()
    assert "222" in s.allowed_user_ids()


def test_allowed_user_ids_empty_set_when_unconfigured():
    os.environ["TELEGRAM_ALLOWED_USER_IDS"] = ""
    from operation_drake.config import get_settings

    get_settings.cache_clear()
    s = get_settings()
    assert s.allowed_user_ids() == set()
