# 상담 본문 칸 앱 암호화(2026-11-16, 민규님과 합의 — 상담일지 · 원문 발화 · 요약 · 회차 메모 · 분석 결과).
#
# 모델에 `content = EncryptedColumn("content", empty="")` 처럼 두면, 서비스 · 스키마 코드는 예전처럼
# `document.content` 를 읽고 쓰지만 DB 에는 `content_enc` 칸에 암호문만 들어간다.
#
# - 암호화는 pii_crypto.encrypt_field(내담자 정보와 같은 키 · 같은 저장 모양). 묶음 값(AAD)은
#   `ispot:<표>:<칸>:<행 ID>:v1` 이라 다른 표 · 칸 · 행으로 옮겨 붙인 암호문은 풀리지 않는다.
# - 쓸 때: `<칸>_enc` 에만 넣고 평문 칸(`<칸>_plain`, DB 이름은 그대로 `<칸>`)은 빈 값("" · [] · None)으로 둔다.
# - 읽을 때: `<칸>_enc` 가 있으면 풀고, 없으면 평문 칸 값(옮기기 전 옛 행). 평문 칸은 다음 PR 에서 지운다.
# - JSON 칸(key_points · result)은 JSON 글자로 바꿔 암호화하고, 읽을 때마다 새로 풀어 준다(제자리 수정은 저장되지 않으니
#   예전처럼 통째로 다시 넣는다 — 지금 코드는 모두 통째로 넣는다).
# - 행 ID 는 암호화 전에 정해져야 한다. 아직 ID 가 없는 새 행은 값을 들고 있다가 INSERT 직전(before_insert)에
#   ID 를 정하고 암호화한다. 행을 복사하는 곳(원문 새 버전 등)은 읽은 평문을 새 행에 넣으므로 새 행 ID 로 다시 암호화된다.
# - 클래스 수준(`Document.content`)은 SQL 식이 아니다. 본문 칸은 DB 검색 조건에 쓰지 않는다(쓰면 바로 오류가 나 드러난다).
#
# 값 · 키를 예외 문구 · 로그에 넣지 않는다(pii_crypto 규칙).

import json
import uuid
from typing import Any, Dict, List, Tuple, Type

from sqlalchemy import event
from sqlalchemy.orm import Mapper

from app.core import pii_crypto

# 모델 클래스 → 그 클래스의 암호화 칸들. 옮기기 · 키 바꾸기 script 가 쓴다.
ENCRYPTED_COLUMNS: Dict[Type[Any], List["EncryptedColumn"]] = {}


class EncryptedColumn:
    """본문 칸 하나. `<칸>_plain`(DB 이름 `<칸>`) · `<칸>_enc` 두 매핑 칸을 감싼다."""

    def __init__(self, column: str, *, empty: Any, json_value: bool = False) -> None:
        self.column = column
        self.json_value = json_value
        self._empty = empty
        self.plain_attr = f"{column}_plain"
        self.enc_attr = f"{column}_enc"
        self._pending_key = f"_encrypted_pending_{column}"
        self._cache_key = f"_encrypted_cache_{column}"
        self.table = ""

    def __set_name__(self, owner: Type[Any], name: str) -> None:
        if name != self.column:
            raise TypeError("EncryptedColumn 이름과 칸 이름이 다릅니다.")

        self.table = owner.__dict__["__tablename__"]
        ENCRYPTED_COLUMNS.setdefault(owner, []).append(self)

    def empty(self) -> Any:
        # 목록 · 사전은 행마다 새로 만든다(한 값을 여러 행이 나눠 쓰지 않게).
        return type(self._empty)(self._empty) if isinstance(self._empty, (list, dict)) else self._empty

    def db_values(self, row_id: uuid.UUID, value: Any) -> Dict[str, Any]:
        """`update(Model).values(...)` 에 넣을 값(평문 칸은 빈 값, 암호문 칸은 이 행 ID 로 암호화한 값).

        ORM 속성을 거치지 않고 조건부 UPDATE 로 저장하는 곳(기관 서식 판 번호 대조 등)이 쓴다.
        키는 모델 속성 이름(`<칸>_plain` · `<칸>_enc`)이다 — `update(Model)` 은 키를 속성 이름으로 찾는다.
        """

        token = None if value is None else self.encrypt(self.dumps(value), row_id)

        return {self.plain_attr: self.empty(), self.enc_attr: token}

    # --- 글자 ↔ 값 ---

    def dumps(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False) if self.json_value else value

    def loads(self, text: str) -> Any:
        return json.loads(text) if self.json_value else text

    def encrypt(self, text: str, row_id: uuid.UUID) -> str:
        return pii_crypto.encrypt_field(text, table=self.table, column=self.column, row_id=row_id)

    def decrypt(self, token: str, row_id: uuid.UUID) -> str:
        return pii_crypto.decrypt_field(token, table=self.table, column=self.column, row_id=row_id)

    # --- 속성 ---

    def __get__(self, obj: Any, owner: Any = None) -> Any:
        if obj is None:
            return self

        state = obj.__dict__

        if self._pending_key in state:
            return state[self._pending_key]

        token = getattr(obj, self.enc_attr)

        if token is None:
            return getattr(obj, self.plain_attr)

        cached: Tuple[str, str] = state.get(self._cache_key)

        if cached is not None and cached[0] == token:
            text = cached[1]
        else:
            text = self.decrypt(token, obj.id)
            state[self._cache_key] = (token, text)

        return self.loads(text)

    def __set__(self, obj: Any, value: Any) -> None:
        state = obj.__dict__

        # 이미 암호문이고 값이 같으면 그대로 둔다. 매번 새 nonce 로 다시 쓰면 값이 같아도 행이 바뀐 것으로 잡혀
        # (예전 평문 칸과 달리) updated_at 이 움직인다.
        if (
            value is not None
            and self._pending_key not in state
            and obj.id is not None
            and getattr(obj, self.enc_attr) is not None
            and self._current_equals(obj, value)
        ):
            return

        state.pop(self._pending_key, None)
        state.pop(self._cache_key, None)
        setattr(obj, self.plain_attr, self.empty())

        if value is None:
            setattr(obj, self.enc_attr, None)
            return

        if obj.id is None:
            # 새 행: INSERT 직전에 ID 를 정하고 암호화한다(_seal_pending).
            state[self._pending_key] = value
            setattr(obj, self.enc_attr, None)
            return

        self._store(obj, obj.id, value)

    def _current_equals(self, obj: Any, value: Any) -> bool:
        try:
            return self.__get__(obj) == value
        except (pii_crypto.PersonalInfoCryptoError, ValueError):
            # 풀리지 않는 옛 값은 새 값으로 덮는다.
            return False

    def _store(self, obj: Any, row_id: uuid.UUID, value: Any) -> None:
        text = self.dumps(value)
        token = self.encrypt(text, row_id)
        setattr(obj, self.enc_attr, token)
        obj.__dict__[self._cache_key] = (token, text)

    def seal_pending(self, obj: Any) -> None:
        if self._pending_key not in obj.__dict__:
            return

        if obj.id is None:
            obj.id = uuid.uuid4()

        value = obj.__dict__.pop(self._pending_key)
        self._store(obj, obj.id, value)


@event.listens_for(Mapper, "before_insert")
def _seal_pending(mapper: Mapper, connection: Any, target: Any) -> None:
    for column in ENCRYPTED_COLUMNS.get(type(target), ()):
        column.seal_pending(target)
