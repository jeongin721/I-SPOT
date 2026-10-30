// 상담 이력 '새 상담 등록' 창(10/29 디자인 CaseHistory.dc.html 의 ns-* 팝업). 회차 고르기 → 상담 내용 · 상담사 소견 → 저장.
// 값 · 저장 규칙은 data/screens/newSession.ts(회차 메모 하나에 두 칸), 저장은 data/useNewSession.ts.
// 저장한 뒤 '확인' 을 누르면 onSaved 로 사례 상세를 다시 부른다.
import { useState } from 'react';
import { useNewSession } from '../data/useNewSession';
import { APPROVED_NOTE, MEMO_MAX, composeMemo, newSessionTargets, parseMemo } from '../data/screens/newSession';
import { NEW_SESSION } from '../data/screens/uploadModal';
import './RecordDialog.css';
import './NewSessionDialog.css';

export default function NewSessionDialog({ caseId, caseName, caseSub, rows, onClose, onSaved }) {
  const targets = newSessionTargets(rows);
  const [step, setStep] = useState(1);
  const [ses, setSes] = useState(NEW_SESSION);
  const [body, setBody] = useState('');
  const [note, setNote] = useState('');
  const [err, setErr] = useState(false);
  const save = useNewSession();
  const cur = targets.find((t) => t.value === ses) ?? targets[0];
  const memo = composeMemo(body, note);
  const tooLong = memo.length > MEMO_MAX;
  const done = save.savedNumber !== null;

  // 적던 글(불러온 메모와 다른 글)이 있는데 다른 회차를 고르면 그 회차 메모로 바뀌므로 먼저 묻는다(민규 #122 리뷰).
  const loaded = parseMemo(cur.memo);
  const dirty = body !== loaded.body || note !== loaded.note;
  const pick = (t) => {
    if (t.value === ses) return;
    if (dirty && !window.confirm('적던 상담 내용은 지워지고 고른 회차의 내용으로 바뀝니다. 바꿀까요?')) return;
    setSes(t.value);
    const parsed = parseMemo(t.memo);
    setBody(parsed.body);
    setNote(parsed.note);
    setErr(false);
  };
  const close = () => {
    if (!save.saving) onClose();
  };

  return (
    <div className="rec-ov">
      <section role="dialog" aria-modal="true" aria-labelledby="ns-title" className="rec-dlg" style={{ maxWidth: '640px' }}>
        <div style={{ padding: '22px 26px 16px', borderBottom: '1px solid #EAE7DF' }} className="rec-hd">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <h2 id="ns-title" style={{ margin: '0', fontSize: '20px', fontWeight: '700' }}>
              새 상담 등록
            </h2>
            <button type="button" className="rec-x" aria-label="닫기" onClick={close}>
              ×
            </button>
          </div>
          <ol
            aria-label="등록 단계"
            style={{ listStyle: 'none', margin: '14px 0 0', padding: '0', display: 'flex', flexWrap: 'wrap', gap: '6px' }}
          >
            {[
              ['상담 회차', 1],
              ['상담 내용 · 소견', 2],
            ].map(([label, n]) => (
              <li key={n} className={`ns-step ${step === n ? 'on' : step > n ? 'done' : ''}`}>
                <span className="ns-dot">{step > n ? '✓' : String(n)}</span>
                {label}
              </li>
            ))}
          </ol>
        </div>
        <div style={{ padding: '22px 26px', minHeight: '340px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div className="rec-case">
            <span className="note">사례</span>
            <b>{caseName}</b>
            <span className="sub">{caseSub}</span>
            {step === 2 ? (
              <span className="chip c-sand" style={{ marginLeft: 'auto' }}>
                {cur.short}
              </span>
            ) : null}
          </div>
          {step === 1 ? (
            <>
              <p className="lb2" style={{ margin: '0' }}>
                몇 회차 상담인가요?
              </p>
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                  maxHeight: '300px',
                  overflowY: 'auto',
                  paddingRight: '6px',
                }}
              >
                {targets.map((x) => (
                  <button
                    key={x.value}
                    type="button"
                    className={`ns-opt ${ses === x.value ? 'on' : ''}`}
                    role="radio"
                    aria-checked={ses === x.value ? 'true' : 'false'}
                    onClick={() => pick(x)}
                  >
                    <span className="ns-rd" aria-hidden="true"></span>
                    <span>
                      <b style={{ fontWeight: '500' }}>{x.label}</b>
                      <span className="note" style={{ display: 'block' }}>
                        {x.meta}
                      </span>
                    </span>
                  </button>
                ))}
              </div>
              {!cur.editable ? (
                <p className="note" role="status" style={{ margin: 0 }}>
                  {APPROVED_NOTE}
                </p>
              ) : null}
            </>
          ) : null}
          {step === 2 ? (
            <>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <span className="lb2">
                  상담 내용 <span className="acc">*</span>
                </span>
                <textarea
                  className="ns-ta"
                  rows="6"
                  placeholder="상담 일시 · 장소, 아동 진술, 주요 대화 내용 등을 적어 주세요"
                  value={body}
                  onChange={(e) => {
                    setBody(e.target.value);
                    setErr(false);
                  }}
                  style={{ borderColor: err ? '#A33B2E' : '#DAD5C9' }}
                ></textarea>
                {err ? (
                  <span className="acc" style={{ fontSize: '13px' }}>
                    상담 내용을 입력해 주세요.
                  </span>
                ) : null}
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <span className="lb2">상담사 소견</span>
                <textarea
                  className="ns-ta"
                  rows="4"
                  placeholder="아동 상태에 대한 판단, 위험 요인, 향후 계획 등을 적어 주세요"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                ></textarea>
              </label>
              {tooLong ? (
                <span className="acc" style={{ fontSize: '13px' }}>
                  상담 내용과 소견을 합쳐 {MEMO_MAX}자까지 저장할 수 있습니다(지금 {memo.length}자).
                </span>
              ) : null}
              {save.error ? (
                <span className="acc" role="alert" style={{ fontSize: '13px' }}>
                  {save.error}
                </span>
              ) : null}
            </>
          ) : null}
        </div>
        <div
          style={{ padding: '16px 26px 22px', display: 'flex', alignItems: 'center', gap: '10px', borderTop: '1px solid #EAE7DF' }}
          className="rec-hd"
        >
          {step === 1 ? (
            <button type="button" className="btn btn-s" onClick={close}>
              취소
            </button>
          ) : (
            <button type="button" className="btn btn-s" onClick={() => setStep(1)} disabled={save.saving}>
              이전
            </button>
          )}
          <span style={{ flex: '1' }}></span>
          {step === 1 ? (
            <button type="button" className="btn btn-p" onClick={() => cur.editable && setStep(2)}>
              다음
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-p"
              disabled={save.saving}
              onClick={() => {
                if (!body.trim()) {
                  setErr(true);
                  return;
                }
                if (tooLong || !caseId) return;
                void save.save(caseId, ses, memo);
              }}
            >
              {save.saving ? '저장 중…' : '저장'}
            </button>
          )}
        </div>
        {done ? (
          <div className="ns-cf-ov">
            <section role="alertdialog" aria-labelledby="ns-ok" className="ns-cf">
              <span className="ns-ok-i" aria-hidden="true">
                ✓
              </span>
              <h2 id="ns-ok" style={{ margin: '0', fontSize: '20px', fontWeight: '700' }}>
                상담을 등록했어요
              </h2>
              <p style={{ margin: '0' }}>
                {caseName} · {save.savedNumber}회차
                <br />
                상담 내용 {body.trim().length}자 · 상담사 소견 {note.trim().length}자
              </p>
              <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '6px' }}>
                <button
                  type="button"
                  className="btn btn-p"
                  onClick={() => {
                    onSaved();
                    onClose();
                  }}
                >
                  확인
                </button>
              </div>
            </section>
          </div>
        ) : null}
      </section>
    </div>
  );
}
