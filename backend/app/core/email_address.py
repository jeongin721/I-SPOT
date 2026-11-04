# 이메일 정규형 — 계정 이메일을 저장 · 조회 · 비교하는 꼴은 이것 하나다(2026-11-03, Codex #139 재검증 N1 · N2).
#
# 아이디(@ 앞)는 소문자, 도메인은 email-validator 가 만드는 IDNA 2008 ASCII(punycode, 소문자)다.
#   'Kim@Bücher.DE' · 'kim@xn--bcher-kva.de' → 'kim@xn--bcher-kva.de'
#   'IDN@straße.de' → 'idn@xn--strae-oqa.de'  (strasse.de 와 다르다)
#
# 왜 하나여야 하나: 회원가입은 SES 가 받는 punycode 로 저장하는데 로그인이 EmailStr(유니코드 도메인)로 찾으면 국제화 도메인 계정이
# 로그인하지 못했다(N1). 비교 키를 파이썬 내장 IDNA(2003 — straße → strasse)로 만들면 email-validator(2008)와 어긋나 같은 메일함을
# 다르게 · 다른 메일함을 같게 봤다(N2). DB 의 lower() 는 ASCII 만 바꿔 쓰지 않는다(M2).
#
# 예전 판이 유니코드 도메인 · 대문자로 저장한 계정도 이 꼴로 바꿔 비교하면 같게 찾는다(user_service.find_user_by_email).

from email_validator import EmailNotValidError, validate_email


def canonical_email(email: str) -> str:
    """
    저장 · 비교용 정규형. 검사기를 통과하지 못하는 옛 값(형식이 깨진 seed 등)은 앞뒤 공백을 떼고 소문자로만 맞춘다.

    아이디에 ASCII 가 아닌 글자가 있어도 받는다(관리자 계정 생성 · 옛 계정 비교). 회원가입 창구는 그런 주소를 따로 422 로 막는다
    (SES 가 보낼 수 없어서, schemas/signup.py).
    """

    value = email.strip()

    try:
        checked = validate_email(value, check_deliverability=False, allow_smtputf8=True)
    except EmailNotValidError:
        return value.lower()

    return f"{checked.local_part.lower()}@{checked.ascii_domain.lower()}"
