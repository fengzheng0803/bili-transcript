import pytest

from bili_api import BiliApiError, extract_bvid_from_url, validate_bvid


def test_valid_bvid():
    assert validate_bvid("BV1xx411c7mD") == "BV1xx411c7mD"


@pytest.mark.parametrize(
    "bad",
    ["", "av123", "BV1", "BV1xx411c7m", "bv1xx411c7mD", "BV1xx411c7mD!", "BV1xx411c7mDD"],
)
def test_invalid_bvid(bad):
    with pytest.raises(BiliApiError):
        validate_bvid(bad)


def test_extract_from_full_url():
    url = "https://www.bilibili.com/video/BV1xx411c7mD?spm_id_from=333.999"
    assert extract_bvid_from_url(url) == "BV1xx411c7mD"


def test_extract_returns_none_for_plain_page():
    assert extract_bvid_from_url("https://www.bilibili.com/") is None


def test_extract_returns_none_for_empty():
    assert extract_bvid_from_url("") is None
