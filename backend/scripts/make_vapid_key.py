# 상담사 앱(폰) 알림용 VAPID 키 만들기(API_CONTRACT 27절, 2026-11-19).
#
#   python -m scripts.make_vapid_key
#
# 개인키 한 줄을 찍는다. backend.env 에 `VAPID_PRIVATE_KEY=<그 값>` 과 `VAPID_SUBJECT=mailto:…` 를 편집기로 넣고
# (터미널 기록에 남지 않게), PII 키처럼 Parameter Store 에도 둔다. 키를 바꾸면 폰마다 알림을 다시 켜야 한다.
# 공개키는 서버가 개인키에서 계산해 GET /push/config 로 내준다.
from app.services.webpush import new_vapid_private_key


def main() -> None:
    print(new_vapid_private_key())


if __name__ == "__main__":
    main()
