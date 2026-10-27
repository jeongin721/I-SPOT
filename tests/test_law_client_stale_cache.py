# law/client.py 의 get_law_by_name 이 새로 받지 못할 때(OC 없음 · API 장애) 오래된 캐시를 쓰는지 고정한다
# (2026-10-27, STT 검수 '관련 조문'이 데모 서버에서 24시간 뒤 사라지지 않게).

import json
import os

import pytest

from law.client import LawApiClient, LawApiError


def _stale_cache(tmp_path):
    path = tmp_path / "아동복지법.json"
    path.write_text(json.dumps({"law_name": "아동복지법", "body": {}}, ensure_ascii=False), encoding="utf-8")
    os.utime(path, (0, 0))
    return path


def test_stale_cache_is_used_when_refetch_fails(tmp_path):
    _stale_cache(tmp_path)
    client = LawApiClient(oc="", cache_dir=tmp_path)

    assert client.get_law_by_name("아동복지법")["law_name"] == "아동복지법"


def test_explicit_refresh_still_fails_without_oc(tmp_path):
    _stale_cache(tmp_path)
    client = LawApiClient(oc="", cache_dir=tmp_path)

    with pytest.raises(LawApiError):
        client.get_law_by_name("아동복지법", refresh=True)


def test_missing_cache_still_fails_without_oc(tmp_path):
    client = LawApiClient(oc="", cache_dir=tmp_path)

    with pytest.raises(LawApiError):
        client.get_law_by_name("아동복지법")
