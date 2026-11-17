// 홈 '미처리 업무' 줄 옆 작은 창(2026-11-11 경진님). 그 업무 종류에 걸린 회차를 오래 기다린 순으로 보이고,
// 아동을 고르면 그 회차의 이어서 할 화면으로 간다. 바깥을 누르거나 Esc 로 닫는다. 값은 useTaskPick 이 부른다.
import { useEffect, useRef } from 'react';
import A from './A';
import { TASK_PICK_SIZE, useTaskPick } from '../data/useTaskPick';

export default function TaskPickPopover({ taskType, title, wholeOrg, onClose }) {
  const pick = useTaskPick(taskType);
  const box = useRef(null);

  useEffect(() => {
    const onDown = (ev) => {
      // 줄 단추(data-task-pick)는 자기 onClick 으로 열고 닫는다 — 여기서 닫으면 같은 줄을 눌렀을 때 바로 다시 열린다.
      if (box.current && !box.current.contains(ev.target) && !ev.target.closest?.('[data-task-pick]')) onClose();
    };
    const onKey = (ev) => {
      if (ev.key === 'Escape') onClose();
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [onClose]);

  const data = pick.data;
  const rest = data ? data.total - data.rows.length : 0;

  return (
    <div ref={box} className="tk-pop" role="dialog" aria-label={`${title} 아동 고르기`}>
      <div className="tk-hd">
        <b style={{ fontSize: '15px' }}>{title}</b>
        <span className="tk-sub">{data ? `${data.total}건 · 오래 기다린 순` : ''}</span>
        <button type="button" className="tk-x" aria-label="닫기" onClick={onClose}>
          ×
        </button>
      </div>
      <div className="tk-list">
        {pick.loading && !data ? <p className="tk-empty">불러오는 중…</p> : null}
        {pick.error ? <p className="tk-empty">{pick.error}</p> : null}
        {data && data.rows.length === 0 ? <p className="tk-empty">남은 업무가 없습니다.</p> : null}
        {(data?.rows ?? []).map((row) => (
          <A key={row.sessionId} className="tk-item" to={row.href} onClick={onClose}>
            <span className="tk-main">
              <b className="tk-t">
                {row.childAlias} {row.sessionNumber}회차
              </b>
              <span className="tk-s">
                {[row.caseNumber, wholeOrg ? row.counselorName : '', `${row.waitingFor} 기다림`].filter(Boolean).join(' · ')}
              </span>
            </span>
            {row.overdue ? <span className="chip c-hi tk-late">지연</span> : null}
            <b className="brn">›</b>
          </A>
        ))}
        {rest > 0 ? <p className="tk-empty">외 {rest}건 — 오래 기다린 {TASK_PICK_SIZE}건만 보입니다.</p> : null}
      </div>
    </div>
  );
}
