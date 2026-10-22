// 사례 상세 '녹음하기' 창(10/21 디자인 CaseDetail.dc.html 의 녹음 팝업).
//
// 마이크로 녹음(useAudioRecorder)한 뒤 '저장' 하면 녹취 올리기 창과 같은 흐름(useAudioUpload: 회차 · 업로드 · 원문 변환)으로
// 서버에 올린다. 두 훅은 사례 상세 화면이 부르고 넘긴다(화면을 떠날 때 묻기 — useLeaveGuard — 에 녹음 상태를 쓰려고).
//  - 회차는 녹취 올리기 창과 같은 목록(uploadTargets)에서 고른다. 녹음을 시작하면 바꿀 수 없다.
//  - 상담 유형 · 녹음 동의는 Backend 에 칸이 없어 저장하지 않는다. 동의 확인은 녹음 시작 전 확인용이다.
//  - 올리는 중(회차 만들기 · 업로드 · 변환 요청)에는 창을 닫지 않는다. 원문 변환을 기다리는 동안에는 닫아도 서버가 계속한다.
import { useEffect, useState } from 'react';
import A from './A';
import { NOT_READY } from '../data/screens/common';
import { screenHref } from '../data/screens/links';
import { NEW_SESSION } from '../data/screens/uploadModal';

const STATUS = {
  idle: '녹음 대기',
  starting: '마이크 여는 중',
  recording: '녹음 중',
  paused: '일시정지',
  stopping: '마무리 중',
  done: '녹음 완료',
};

const KINDS = ['정기상담', '방문상담', '기관 면담', '전화상담'];

/** 녹음해 둔 것이 있어 닫거나 떠나면 사라지는가. */
export function recordingUnsaved(recorder, upload) {
  return recorder.status !== 'idle' && upload.phase === 'idle';
}

export default function RecordDialog({ caseId, caseName, caseSub, targets, recorder, upload, onClose }) {
  const [choice, setChoice] = useState(NEW_SESSION);
  const [consent, setConsent] = useState(false);
  const [consentError, setConsentError] = useState(false);

  // 회차 만들기 · 업로드 · 변환 요청 중에는 닫지 않는다(그사이 닫으면 원문 변환 요청이 빠진다).
  const sending = upload.busy && upload.phase !== 'transcribing';
  const saved = upload.phase === 'done';
  const target = targets.find((t) => t.value === choice) ?? targets[0];
  const mm = `${String(Math.floor(recorder.seconds / 60)).padStart(2, '0')}:${String(recorder.seconds % 60).padStart(2, '0')}`;
  const locked = recorder.status !== 'idle' || upload.phase !== 'idle';

  const close = () => {
    if (sending) return;
    if (recordingUnsaved(recorder, upload) && !window.confirm('녹음을 저장하지 않고 닫을까요? 녹음은 사라집니다.')) return;
    recorder.reset();
    upload.reset();
    onClose();
  };

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') close();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const start = () => {
    if (!consent) {
      setConsentError(true);
      return;
    }
    recorder.start();
  };

  const save = () => {
    if (!recorder.file || upload.busy) return;
    void upload.start({
      caseId,
      sessionId: choice === NEW_SESSION ? null : choice,
      file: recorder.file,
      durationMs: recorder.seconds * 1000,
    });
  };

  const live = recorder.status === 'recording';
  const dotCls = live ? 'rec-dot live' : recorder.status === 'idle' ? 'rec-dot' : 'rec-dot off';
  const status = saved ? '저장 완료' : upload.busy ? `저장 중 · ${upload.phaseLabel}` : STATUS[recorder.status];
  const summary = `${caseName} · ${target ? target.short : ''} · ${mm}`;

  return (
    <div className="rec-ov">
      <section role="dialog" aria-modal="true" aria-labelledby="rec-title" className="rec-dlg">
        <div
          className="rec-hd"
          style={{
            padding: '20px 24px 16px',
            borderBottom: '1px solid #EAE7DF',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <h2 id="rec-title" style={{ margin: '0', fontSize: '20px', fontWeight: '700' }}>
            녹음하기
          </h2>
          <button type="button" className="rec-x" aria-label="닫기" onClick={close} disabled={sending}>
            ×
          </button>
        </div>
        <div style={{ padding: '20px 24px 24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="rec-case">
            <span className="note">사례</span>
            <b>{caseName}</b>
            <span className="sub">{caseSub}</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span className="lb2">상담 회차</span>
              <select className="inp" value={choice} onChange={(e) => setChoice(e.target.value)} disabled={locked}>
                {targets.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span className="lb2">
                상담 유형 <span className="note" style={{ fontWeight: '400' }}>{NOT_READY}</span>
              </span>
              <select className="inp" disabled title={NOT_READY}>
                {KINDS.map((k) => (
                  <option key={k}>{k}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="rec-box">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px' }}>
              <span className={dotCls} aria-hidden="true"></span>
              <span className="rec-status">{status}</span>
            </div>
            <div className="rec-time" aria-live="polite">
              {mm}
            </div>
            {recorder.status === 'idle' || recorder.status === 'starting' ? (
              <>
                <label className="rec-consent">
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={(e) => {
                      setConsent(e.target.checked);
                      setConsentError(false);
                    }}
                  />
                  <span>상대방에게 녹음 사실을 알리고 동의를 받았어요</span>
                </label>
                {consentError ? (
                  <span className="acc" role="alert" style={{ fontSize: '13px' }}>
                    녹음 동의를 먼저 확인해 주세요.
                  </span>
                ) : null}
                {recorder.error ? (
                  <span className="acc" role="alert" style={{ fontSize: '13px' }}>
                    {recorder.error}
                  </span>
                ) : null}
                <button
                  type="button"
                  className="btn btn-p rec-main"
                  onClick={start}
                  disabled={recorder.status === 'starting'}
                >
                  <span className="rec-dot" aria-hidden="true"></span> 녹음 시작
                </button>
                <span className="note">동의 여부 · 상담 유형은 서버에 기록되지 않습니다.</span>
              </>
            ) : null}
            {recorder.status === 'recording' || recorder.status === 'paused' ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '8px' }}>
                <button type="button" className="btn btn-s" onClick={live ? recorder.pause : recorder.resume}>
                  {live ? '일시정지' : '계속 녹음'}
                </button>
                <button type="button" className="btn btn-p" onClick={recorder.stop}>
                  ■ 정지
                </button>
              </div>
            ) : null}
            {recorder.status === 'done' && upload.phase === 'idle' ? (
              <>
                {recorder.url ? <audio controls src={recorder.url} style={{ width: '100%' }}></audio> : null}
                <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '8px' }}>
                  <button type="button" className="btn btn-s" onClick={recorder.reset}>
                    다시 녹음
                  </button>
                  <button type="button" className="btn btn-p" onClick={save}>
                    저장
                  </button>
                </div>
              </>
            ) : null}
            {upload.busy ? (
              <p className="note" role="status" style={{ margin: '0' }}>
                {upload.phaseLabel}… {sending ? '끝날 때까지 창을 닫지 마세요.' : '창을 닫아도 서버의 변환은 계속됩니다.'}
              </p>
            ) : null}
            {upload.phase === 'failed' ? (
              <>
                <span className="acc" role="alert" style={{ fontSize: '13px' }}>
                  {upload.error ?? '처리하지 못했습니다.'}
                </span>
                <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '8px' }}>
                  <button type="button" className="btn btn-s" onClick={close}>
                    닫기
                  </button>
                  {upload.failedStep && upload.failedStep !== 'file' ? (
                    <button type="button" className="btn btn-p" onClick={() => void upload.retry()}>
                      다시 시도
                    </button>
                  ) : null}
                </div>
              </>
            ) : null}
            {saved ? (
              <>
                <p style={{ margin: '0', textAlign: 'center' }}>
                  녹음을 저장했어요 · {summary}
                  <br />
                  <b>원문 변환이 끝났어요. STT 검수로 이동할까요?</b>
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '8px' }}>
                  <button type="button" className="btn btn-s" onClick={close}>
                    나중에
                  </button>
                  <A className="btn btn-p" to={screenHref('/SttReview', { caseId, sessionId: upload.sessionId })}>
                    STT 검수로 →
                  </A>
                </div>
              </>
            ) : null}
          </div>
        </div>
      </section>
    </div>
  );
}
