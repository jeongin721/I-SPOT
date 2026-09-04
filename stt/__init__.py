# 팀 A(STT) 산출물 package.
#
# Backend 는 REPO_ROOT 를 sys.path 에 추가한 뒤
# stt.transcribe_service.transcribe(audio_path) 를 호출한다.
# (backend/app/adapters/module_loader.py, stt_adapter.ModuleSTTAdapter)
#
# 여기서는 의도적으로 아무것도 re-export 하지 않는다.
# ispot_stt 는 dotenv/deepgram 을 module import 시점에 필요로 하기 때문에,
# 후처리(ispot_postprocess) 만 쓰는 코드가 STT provider SDK 까지
# 설치해야 하는 상황을 만들지 않는다.
