# I-SPOT 상담사 웹 화면 설계

Claude Design 캔버스("I-SPOT 상담사 웹 화면 설계")에서 만든 화면 설계 원본입니다. 백엔드 API 설계·연동 작업의 기준 화면으로 사용합니다.

- 원본 캔버스: https://claude.ai/artifact/Pm9eK5Kcy2HdYcR68JZDwm
- `canvas.json`: 화면 목록, 화면 제목, 캔버스 배치, 흐름(행) 구분
- `*.dc.html`: 화면별 마크업 + 화면 로직(`<script type="text/x-dc">` 안의 `renderVals()`에 화면에서 쓰는 데이터 구조가 들어 있음)

> 참고: 각 파일은 Claude Design 런타임(`./support.js`)에서 렌더링되는 형식이라 브라우저에서 바로 열면 레이아웃이 그대로 보이지 않을 수 있습니다. 화면 확인은 원본 캔버스 링크에서 하세요.

## 화면 흐름

| 흐름 | 화면 파일 |
|---|---|
| ① 하루 시작 | `Login` → `Main`(홈 대시보드) → `Schedule` → `ChildLink` → `ChildDetail` |
| ② 사례 관리 | `CaseList` → `CaseRegister` |
| ③ 사례 상세 (탭 5개 + 서식) | `CaseDetail` · `CaseHistory` · `SessionDetail` · `PreBriefing` · `CaseApp` · `CaseDocs` · `CaseForm` |
| ④ 회차 처리 | `UploadModal` → `SttReview` → `SignalReview` → `RiskProfile` → `NoteWrite` → `FollowupQ` |
| ⑤ 종결 · 기타 | `Closure` → `ClosureReview` → `ClosureDetail` · `Stats` · `Settings` · `Admin` |
