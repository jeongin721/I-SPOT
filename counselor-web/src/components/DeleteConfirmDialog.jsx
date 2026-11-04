// 되돌릴 수 없는 삭제(관리자 — 사례 · 회차, 2026-11-03)를 확인하는 창. 값 · 동작은 data/useAdminDelete 가 준다.
// 디자인(counselor-design 11/03 판)에 사례 · 회차 삭제 창이 없어, 이름 표시 방식 창(PrintNameDialog .out-*)의 틀과
// 일정 삭제 확인(Schedule .vd-ask · .vd-del-go)의 붉은 경고색으로 만들었다.
// 대상 글자(사례 번호 · 'N회차')를 그대로 쳐야 '영구 삭제' 가 눌린다. Esc · 취소로 닫는다(지우는 중에는 닫지 않는다).
// 대상마다 입력이 비도록 부르는 쪽이 key 로 대상 ID 를 준다.
import { useEffect, useState } from 'react';
import './DeleteConfirmDialog.css';

export default function DeleteConfirmDialog({ del }) {
  const [typed, setTyped] = useState('');
  const { target, busy, close } = del;
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') close();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [close]);
  if (!target) return null;
  const ok = typed.trim() === target.confirmText;
  const what = target.kind === 'case' ? '사례 번호' : '회차';
  return (
    <div className="rm-ov">
      <div className="rm-dlg" role="alertdialog" aria-modal="true" aria-labelledby="rm-t" aria-describedby="rm-d">
        <b id="rm-t" style={{ fontSize: '18px' }}>
          {del.title}
        </b>
        <div className="rm-ask" id="rm-d">
          <b>{target.label}</b>
          <span>지우면 되돌릴 수 없습니다. 아래 자료가 함께 지워집니다.</span>
          <ul>
            {del.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          {target.processing ? (
            <span>음성 변환 · AI 분석이 진행 중인 회차입니다. 처리가 끝난 뒤 지우는 것이 안전합니다.</span>
          ) : null}
        </div>
        <span className="note" style={{ marginTop: '-4px' }}>
          누가 언제 지웠는지는 감사 기록에 남습니다.
        </span>
        <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <span>
            지우려면 {what}를 그대로 쓰세요: <b className="rm-code">{target.confirmText}</b>
          </span>
          <input
            className="inp"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && ok && !busy) del.run();
            }}
            autoFocus
            autoComplete="off"
            spellCheck={false}
            disabled={busy}
            aria-label={`${what} 입력`}
          />
        </label>
        {del.error ? (
          <span className="note" role="alert" style={{ color: '#A33B2E' }}>
            {del.error}
          </span>
        ) : null}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
          <button type="button" className="btn btn-s" onClick={close} disabled={busy}>
            취소
          </button>
          <button type="button" className="btn rm-go" onClick={del.run} disabled={!ok || busy}>
            {busy ? '지우는 중…' : '영구 삭제'}
          </button>
        </div>
      </div>
    </div>
  );
}
