// 상담사 앱(폰) · 메모(작성 · 수정 · 삭제)
// 원본: 앱 · 메모 (작성 · 수정 · 삭제) 2026-11-10 zip 의 AppMemo.dc.html
//
// 서버 연결: 상담사 메모 API(GET · POST · PATCH · DELETE /memos, API_CONTRACT 25절). 쓴 사람만 보고(관리자도 못 봄),
// 본문은 서버에 암호화해 저장한다. 폰에는 저장하지 않는다(연결이 없으면 저장하지 못했다고 알리고 적은 글은 칸에 그대로 둔다).
//  - 관련 아이: 내 진행 중 사례(useAppCases). 주소에 ?case= 가 있으면 그 아이를 골라 둔다(사례 목록의 '메모').
//    담당이 바뀐 사례의 메모는 서버가 목록에서 뺀다.
//  - 목록은 최신순 30개씩. 더 있으면 맨 아래 '더 보기'(디자인에 없어 더함).
//  - 서버가 풀지 못한 메모(unreadable)는 '읽을 수 없는 메모' 로 보이고, 지우거나 새로 적을 수 있다.
//  - 시각은 이 폰 시각('방금' · '오늘 15:20' · '어제 18:02' · '10/27 09:40').
import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import MobileAppShell, { whenText } from '../components/MobileAppShell';
import { memos as memoApi } from '../api/endpoints';
import { parseBackendTime } from '../data/time';
import { childLabelOf, useAppCases } from '../data/useAppCases';
import { errorMessage } from '../data/useRemote';

const PAGE = 30;
const at = (iso) => parseBackendTime(iso)?.getTime() ?? Date.now();

function MemoBody({ userId }) {
  const my = useAppCases(userId);
  const [params] = useSearchParams();
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [loadErr, setLoadErr] = useState('');
  const [nCase, setNCase] = useState(params.get('case') ?? '');
  const [nText, setNText] = useState('');
  const [edit, setEdit] = useState(null);
  const [ask, setAsk] = useState(false);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    async (upTo) => {
      if (!userId) return;
      setLoading(true);
      try {
        // 1쪽부터 지금까지 본 쪽까지 다시 받는다(만들기 · 고치기 · 지우기 뒤에도 보던 만큼 그대로).
        let items = [];
        let count = 0;
        for (let p = 1; p <= upTo; p += 1) {
          const res = await memoApi.list({ page: p, page_size: PAGE });
          items = items.concat(res.items);
          count = res.meta.total;
          if (p >= res.meta.total_pages) break;
        }
        setRows(items);
        setTotal(count);
        setLoadErr('');
      } catch (caught) {
        setLoadErr(errorMessage(caught, '메모를 불러오지 못했어요. 연결을 확인해 주세요.'));
      } finally {
        setLoading(false);
      }
    },
    [userId],
  );

  useEffect(() => {
    void load(page);
  }, [load, page]);

  // 이름은 내 사례 목록의 실명(없으면 서버가 준 별칭).
  const nameOf = (m) => {
    const row = m.case_id ? my.rows.find((r) => r.id === m.case_id) : null;
    return row ? childLabelOf(row) : m.child_alias ?? '';
  };

  const run = async (work, failText) => {
    if (busy) return false;
    setBusy(true);
    setErr('');
    try {
      await work();
      await load(page);
      return true;
    } catch (caught) {
      setErr(errorMessage(caught, failText));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const add = async () => {
    const text = nText.trim();
    if (!text) return;
    const ok = await run(() => memoApi.create({ text, case_id: nCase || null }), '메모를 저장하지 못했어요. 연결을 확인해 주세요.');
    if (ok) setNText('');
  };
  const saveEdit = async () => {
    const text = (edit.text || '').trim();
    if (!text) return;
    const ok = await run(() => memoApi.update(edit.id, { text, case_id: edit.caseId || null }), '고치지 못했어요. 연결을 확인해 주세요.');
    if (ok) setEdit(null);
  };
  const del = async () => {
    const ok = await run(() => memoApi.remove(edit.id), '지우지 못했어요. 연결을 확인해 주세요.');
    if (ok) {
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
        <textarea className="ma-inp" rows={3} placeholder="메모를 적어 주세요" value={nText} onChange={(ev) => setNText(ev.target.value)} aria-label="메모 내용" maxLength={4000} />
        <button type="button" className="ma-btn ma-btn-p" onClick={add} disabled={busy}>
          메모 저장
        </button>
        {err && !edit && <span className="ma-err">{err}</span>}
      </section>
      <p className="ma-sec-t">최근 메모 · {loading && rows.length === 0 ? '—' : total}개</p>
      {loadErr && <span className="ma-err">{loadErr}</span>}
      {rows.map((m) => (
        <div
          key={m.id}
          className="ma-card ma-mi"
          role="button"
          tabIndex={0}
          onClick={() => {
            setAsk(false);
            setErr('');
            setEdit({ id: m.id, caseId: m.case_id ?? '', label: nameOf(m), text: m.text ?? '', t: whenText(at(m.created_at)) });
          }}
        >
          <div className="ma-mi-top">
            {m.case_id && <span className="ma-chip ma-gold">{nameOf(m)}</span>}
            <span className="ma-note" style={{ marginLeft: 'auto' }}>
              {whenText(at(m.created_at))}
            </span>
          </div>
          {m.unreadable ? <p style={{ color: 'var(--mut)' }}>읽을 수 없는 메모예요. 지우거나 새로 적어 주세요.</p> : <p>{m.text}</p>}
        </div>
      ))}
      {rows.length < total && (
        <button type="button" className="ma-btn" onClick={() => setPage(page + 1)} disabled={loading}>
          더 보기
        </button>
      )}
      {edit && (
        <div className="ma-ov" onClick={() => setEdit(null)}>
          <section className="ma-sheet" role="dialog" aria-modal="true" aria-label="메모 수정" onClick={stop}>
            <span className="ma-grab" aria-hidden="true"></span>
            <div className="ma-sh-hd">
              <b>메모</b>
              <span className="ma-note">{edit.t}</span>
            </div>
            <select className="ma-inp" value={edit.caseId} onChange={(ev) => setEdit({ ...edit, caseId: ev.target.value })} aria-label="관련 아이">
              {kidOptions(edit.caseId, edit.label)}
            </select>
            <textarea className="ma-inp" rows={5} value={edit.text} onChange={(ev) => setEdit({ ...edit, text: ev.target.value })} aria-label="메모 내용" maxLength={4000} />
            {err && <span className="ma-err">{err}</span>}
            {!ask ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '8px' }}>
                <button type="button" className="ma-btn ma-btn-red" onClick={() => setAsk(true)}>
                  삭제
                </button>
                <button type="button" className="ma-btn ma-btn-p" onClick={saveEdit} disabled={busy}>
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
                  <button type="button" className="ma-btn" style={{ background: 'var(--red)', borderColor: 'var(--red)', color: '#FFFFFF' }} onClick={del} disabled={busy}>
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
