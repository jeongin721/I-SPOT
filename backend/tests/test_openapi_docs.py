# /docs 에 노출되는 API 문서 자체를 검증한다.
#
# Frontend 담당자가 이 문서만 보고 화면을 붙이므로, 문서가 헷갈리면
# 코드가 정상이어도 연동에서 시간이 샌다.

from fastapi.testclient import TestClient


def _paths(client: TestClient) -> dict:
    response = client.get("/openapi.json")

    assert response.status_code == 200

    return response.json()["paths"]


def test_each_endpoint_belongs_to_one_tag(client: TestClient) -> None:
    """
    endpoint 하나가 여러 tag 를 가지면 Swagger 에서 같은 항목이 그룹마다
    중복 표시되어, 서로 다른 API 로 오해하게 된다.

    APIRouter 의 tag 와 route 의 tag 는 합쳐지므로(덮어쓰기가 아니다)
    router tag 가 있는 곳에 route tag 를 더하면 이 상황이 생긴다.
    """

    duplicated = []

    for path, operations in _paths(client).items():
        for method, operation in operations.items():
            tags = operation.get("tags", [])

            if len(tags) > 1:
                duplicated.append(f"{method.upper()} {path} → {tags}")

    assert not duplicated, "tag 가 둘 이상인 endpoint:\n" + "\n".join(duplicated)


def test_case_scoped_session_endpoints_are_tagged_sessions(
    client: TestClient,
) -> None:
    """
    주소가 아니라 다루는 대상으로 그룹을 나눈다.
    (/sessions/{id}/audio 가 audio tag 인 것과 같은 규칙)
    """

    operations = _paths(client)["/api/v1/cases/{case_id}/sessions"]

    assert operations["get"]["tags"] == ["sessions"]
    assert operations["post"]["tags"] == ["sessions"]
