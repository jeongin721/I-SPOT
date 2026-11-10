// 상담사 앱(폰) · 메모(작성 · 수정 · 삭제)
// 원본: 앱 · 메모 (작성 · 수정 · 삭제) 2026-11-10 zip 의 AppMemo.dc.html
//
// 서버 연결: 메모를 둘 서버 자리가 없어 이 폰에만 계정별로 저장한다(appMemos.ts). 웹에서는 보이지 않는다.
//  - 관련 아이: 내 진행 중 사례(useAppCases). 주소에 ?case= 가 있으면 그 아이를 골라 둔다(사례 목록의 '메모').
//  - 시각은 이 폰 시각('방금' · '오늘 15:20' · '어제 18:02' · '10/27 09:40').
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import MobileAppShell, { whenText } from '../components/MobileAppShell';
import { readMemos, writeMemos } from '../data/appMemos';
import { childLabelOf, useAppCases } from '../data/useAppCases';

function MemoBody({ userId }) {
  const my = useAppCases(userId);
  const [params] = useSearchParams();
  const [memos, setMemos] = useState(() => (userId ? readMemos(userId) : []));
  const [nCase, setNCase] = useState(params.get('case') ?? '');
  const [nText, setNText] = useState('');
  const [edit, setEdit] = useState(null);
  const [ask, setAsk] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    if (userId) setMemos(readMemos(userId));
  }, [userId]);

  const labelOf = (caseId) => {
    const row = my.rows.find((r) => r.id === caseId);
    return row ? childLabelOf(row) : '';
  };
  const commit = (rows) => {
    if (!userId) return false;
    if (!writeMemos(userId, rows)) {
      setErr('폰에 메모를 저장하지 못했어요. 저장 공간을 확인해 주세요.');
      return false;
    }
    setErr('');
    setMemos(readMemos(userId));
    return true;
  };
  const add = () => {
    const text = nText.trim();
    if (!text) return;
    const now = Date.now();
    const memo = { id: 'm' + now.toString(36), caseId: nCase || null, childLabel: nCase ? labelOf(nCase) : '', text, createdAt: now, updatedAt: now };
    if (commit([memo, ...memos])) setNText('');
  };
  const saveEdit = () => {
    if (!(edit.text || '').trim()) return;
    const ok = commit(
      memos.map((m) =>
        m.id === edit.id
          ? { ...m, caseId: edit.caseId || null, childLabel: edit.caseId ? labelOf(edit.caseId) || m.childLabel : '', text: edit.text.trim(), updatedAt: Date.now() }
          : m,
      ),
    );
    if (ok) setEdit(null);
  };
  const del = () => {
    if (commit(memos.filter((m) => m.id !== edit.id))) {
      setEdit(null);
      setAsk(false);
    }
  };
  const kidOptions = (value, current) => (
    <>
      <option value="">관련 아이 선택 안 함</option>
      {value && !my.rows.some((r) => r.id === value) && <option value={value}>{current || '지난 사례'}</option>}
      {my.rows.map((r) => (
        <option key={r.id} value={r.id}>
          {childLabelOf(r)}
        </option>
      ))}
    </>
  );
  const stop = (ev) => ev.stopPropagation();

  return (
    <>
      <section className="ma-card" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }} aria-label="새 메모">
        <select className="ma-inp" value={nCase} onChange={(ev) => setNCase(ev.target.value)} aria-label="관련 아이">
          {kidOptions(nCase, '')}
        </select>
        <textarea className="ma-inp" rows={3} placeholder="메모를 적어 주세요" value={nText} onChange={(ev) => setNText(ev.target.value)} aria-label="메모 내용" />
        <button type="button" className="ma-btn ma-btn-p" onClick={add}>
          메모 저장
        </button>
        {err && !edit && <span className="ma-err">{err}</span>}
      </section>
      <p className="ma-sec-t">최근 메모 · {memos.length}개</p>
      {memos.map((m) => (
        <div
          key={m.id}
          className="ma-card ma-mi"
          role="button"
          tabIndex={0}
          onClick={() => {
            setAsk(false);
            setEdit({ id: m.id, caseId: m.caseId ?? '', childLabel: m.childLabel, text: m.text, t: whenText(m.createdAt) });
          }}
        >
          <div className="ma-mi-top">
            {m.childLabel && <span className="ma-chip ma-gold">{m.childLabel}</span>}
            <span className="ma-note" style={{ marginLeft: 'auto' }}>
              {whenText(m.createdAt)}
            </span>
          </div>
          <p>{m.text}</p>
        </div>
      ))}
      <p className="ma-note" style={{ margin: 0 }}>
        메모는 이 휴대폰에만 저장돼요.
      </p>
      {edit && (
        <div className="ma-ov" onClick={() => setEdit(null)}>
          <section className="ma-sheet" role="dialog" aria-modal="true" aria-label="메모 수정" onClick={stop}>
            <span className="ma-grab" aria-hidden="true"></span>
            <div className="ma-sh-hd">
              <b>메모</b>
              <span className="ma-note">{edit.t}</span>
            </div>
            <select className="ma-inp" value={edit.caseId} onChange={(ev) => setEdit({ ...edit, caseId: ev.target.value })} aria-label="관련 아이">
              {kidOptions(edit.caseId, edit.childLabel)}
            </select>
            <textarea className="ma-inp" rows={5} value={edit.text} onChange={(ev) => setEdit({ ...edit, text: ev.target.value })} aria-label="메모 내용" />
            {err && <span className="ma-err">{err}</span>}
            {!ask ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '8px' }}>
                <button type="button" className="ma-btn ma-btn-red" onClick={() => setAsk(true)}>
                  삭제
                </button>
                <button type="button" className="ma-btn ma-btn-p" onClick={saveEdit}>
                  수정 저장
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', padding: '14px', borderRadius: '12px', background: 'var(--redsoft)' }}>
                <b style={{ color: 'var(--red)' }}>이 메모를 삭제할까요?</b>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <button type="button" className="ma-btn" onClick={() => setAsk(false)}>
                    취소
                  </button>
                  <button type="button" className="ma-btn" style={{ background: 'var(--red)', borderColor: 'var(--red)', color: '#FFFFFF' }} onClick={del}>
                    삭제
                  </button>
                </div>
              </div>
            )}
          </section>
        </div>
      )}
    </>
  );
}

export default function AppMemo() {
  return (
    <MobileAppShell cur="memo" screen="memo" sub="현장에서 바로 적어 두기" title="메모">
      {(ctx) => <MemoBody {...ctx} />}
    </MobileAppShell>
  );
}
