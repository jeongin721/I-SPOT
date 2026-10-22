// STT 검수 하단 고정 녹음 재생 바(10/22 디자인 SttReview.dc.html 의 .player). STT 검수 화면만 쓴다.
// 값은 src/data/screens/sttReview.ts 의 sttReviewValues().player 가 만들고, 모양은 src/pages/SttReview.css(.pg-SttReview .player …)에 있다.
//
// 서버가 녹음 파일 · 재생 주소를 주지 않아 5초 뒤로 · 재생 · 정지 · 5초 앞으로 · 재생 위치는 꺼 두고 '준비 중' 이라고 쓴다
// (p.ready 가 false). 재생이 없으니 디자인의 일시정지 그림 · 재생 위치 채움도 그리지 않는다.
// 재생 위치 줄 위 표시(확인 안 한 저신뢰 · 화자 미확인 발화)는 동작한다. 누르면 그 발화 줄로 옮긴다(m.go).
export default function SttPlayer({ p }) {
  if (!p) return null;
  return (
    <div className="player" role="region" aria-label="녹음 재생">
      <div className="pl-ctrls">
        {p.markLabel ? (
          <span className="pl-legend">
            <i aria-hidden="true"></i>
            {p.markLabel}
          </span>
        ) : null}
        <button type="button" className="pl-b" aria-label={p.back} title={p.back} disabled={!p.ready}>
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
            <path d="M11 6v12L2.5 12z"></path>
            <path d="M21 6v12l-8.5-6z"></path>
          </svg>
        </button>
        <button type="button" className="pl-b pl-main" aria-label={p.play} title={p.play} disabled={!p.ready}>
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
            <path d="M8 5v14l11-7z"></path>
          </svg>
        </button>
        <button type="button" className="pl-b" aria-label={p.stop} title={p.stop} disabled={!p.ready}>
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
            <rect x="6" y="6" width="12" height="12" rx="1.5"></rect>
          </svg>
        </button>
        <button type="button" className="pl-b" aria-label={p.fwd} title={p.fwd} disabled={!p.ready}>
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
            <path d="M13 6v12l8.5-6z"></path>
            <path d="M3 6v12l8.5-6z"></path>
          </svg>
        </button>
        <span className="pl-note">{p.note}</span>
      </div>
      <div className="pl-time">
        <span className="pl-t">{p.cur}</span>
        <span className="pl-track">
          <input
            type="range"
            className="pl-range"
            min="0"
            max="1"
            step="1"
            value={0}
            disabled={!p.ready}
            aria-label={p.seek}
            title={p.seek}
          />
          {(p.marks || []).map((m) => (
            <button
              key={m.key}
              type="button"
              className="pl-mark"
              style={{ left: m.left }}
              aria-label={m.aria}
              title={m.title}
              onClick={m.go}
            ></button>
          ))}
        </span>
        <span className="pl-t">{p.dur}</span>
      </div>
    </div>
  );
}
