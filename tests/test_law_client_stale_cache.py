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


def test_cache_only_reads_stale_cache_without_network(tmp_path, monkeypatch):
    # 회차 분석 경로(cache_only=True)는 오래된 캐시도 그대로 읽고 국가법령정보센터를 부르지 않는다
    # (2026-10-27 민규 리뷰 — 요청이 분석 마감을 보지 않아 최대 60초가 더해질 수 있었다).
    _stale_cache(tmp_path)
    client = LawApiClient(oc="있는 척", cache_dir=tmp_path)

    def no_network(*args, **kwargs):
        raise AssertionError("cache_only 인데 네트워크를 불렀습니다")

    monkeypatch.setattr(client, "find_law", no_network)

    assert client.get_law_by_name("아동복지법", cache_only=True)["law_name"] == "아동복지법"


def test_cache_only_without_cache_fails_without_network(tmp_path, monkeypatch):
    client = LawApiClient(oc="있는 척", cache_dir=tmp_path)
    monkeypatch.setattr(client, "find_law", lambda *a, **k: (_ for _ in ()).throw(AssertionError("네트워크")))

    with pytest.raises(LawApiError):
        client.get_law_by_name("아동복지법", cache_only=True)
