// STT 검수 하단 고정 녹음 재생 바(10/22 디자인 SttReview.dc.html 의 .player). STT 검수 화면만 쓴다.
// 값은 src/data/screens/sttReview.ts 의 sttReviewValues().player 가 만들고, 모양은 src/pages/SttReview.css(.pg-SttReview .player …)에 있다.
//
// 재생은 Backend 의 음성 파일 API(GET /sessions/{id}/audio/file)를 useSessionAudio · useAudioPlayer 가 받아 돌린다(10/28).
// p.ready 가 false 면(녹음 없음 · 파일을 못 받음) 단추를 끄고 p.note 에 이유를 쓴다.
// 재생 위치 줄 위 표시(확인 안 한 저신뢰 · 화자 미확인 발화)는 누르면 그 발화 줄로 옮긴다(m.go).
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
        <button type="button" className="pl-b" aria-label={p.back} title={p.back} disabled={!p.ready} onClick={p.onBack}>
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
            <path d="M11 6v12L2.5 12z"></path>
            <path d="M21 6v12l-8.5-6z"></path>
          </svg>
        </button>
        <button
          type="button"
          className="pl-b pl-main"
          aria-label={p.play}
          title={p.play}
          aria-pressed={p.playing}
          disabled={!p.ready}
          onClick={p.onPlay}
        >
          {p.playing ? (
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
              <rect x="6" y="5" width="4" height="14" rx="1"></rect>
              <rect x="14" y="5" width="4" height="14" rx="1"></rect>
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
              <path d="M8 5v14l11-7z"></path>
            </svg>
          )}
        </button>
        <button type="button" className="pl-b" aria-label={p.stop} title={p.stop} disabled={!p.ready} onClick={p.onStop}>
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
            <rect x="6" y="6" width="12" height="12" rx="1.5"></rect>
          </svg>
        </button>
        <button type="button" className="pl-b" aria-label={p.fwd} title={p.fwd} disabled={!p.ready} onClick={p.onFwd}>
          <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true">
            <path d="M13 6v12l8.5-6z"></path>
            <path d="M3 6v12l8.5-6z"></path>
          </svg>
        </button>
        {p.note ? (
          <span className="pl-note" role="status">
            {p.note}
          </span>
        ) : null}
      </div>
      <div className="pl-time">
        <span className="pl-t">{p.cur}</span>
        <span className="pl-track">
          <input
            type="range"
            className="pl-range"
            min="0"
            max="1000"
            step="1"
            value={Math.round((p.pos || 0) * 1000)}
            disabled={!p.ready || !p.canSeek}
            aria-label={p.seek}
            title={p.seek}
            onChange={(event) => p.onSeek(Number(event.target.value) / 1000)}
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
