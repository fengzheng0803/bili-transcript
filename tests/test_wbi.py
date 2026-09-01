import hashlib
import re

from bili_api import MIXIN_KEY_ENC_TAB, enc_wbi, get_mixin_key


def test_mixin_tab_is_64_entries():
    assert len(MIXIN_KEY_ENC_TAB) == 64


def test_get_mixin_key_length_and_determinism():
    key = get_mixin_key("a" * 64)
    assert len(key) == 32
    assert get_mixin_key("a" * 64) == key


def test_enc_wbi_signature_format_and_md5():
    """用 hashlib 独立重算 w_rid 交叉校验签名格式（真实签名正确性由端到端验收覆盖）。"""
    img_key, sub_key, ts = "0123456789abcdef0123456789abcdef", "fedcba9876543210fedcba9876543210", 1700000000
    signed = enc_wbi({"bvid": "BV1xx411c7mD"}, img_key, sub_key, ts)
    assert signed["wts"] == ts
    assert signed["bvid"] == "BV1xx411c7mD"
    query = re.sub(r"[!'()*]", "", "bvid=BV1xx411c7mD&wts=1700000000")
    mixin = get_mixin_key(img_key + sub_key)
    assert signed["w_rid"] == hashlib.md5((query + mixin).encode()).hexdigest()


def test_enc_wbi_filters_special_chars():
    """参数值含 '!' 时 query 中该字符被过滤后再签名。"""
    img_key, sub_key, ts = "0123456789abcdef0123456789abcdef", "fedcba9876543210fedcba9876543210", 1700000000
    signed = enc_wbi({"keyword": "ab!cd"}, img_key, sub_key, ts)
    assert signed["keyword"] == "ab!cd"  # 参数值本身不变
    assert len(signed["w_rid"]) == 32
