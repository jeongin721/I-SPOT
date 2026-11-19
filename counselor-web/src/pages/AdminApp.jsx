// 관리자 · 아이 연계 앱 관리
// 원본: 11/17 디자인 counselor-design/screens/AdminApp.dc.html (frontend261021). 관리자 메뉴의 사례 목록 다음.
//
// 서버 연결(11/19): GET /child-app-cases(관리자 — 진행 중 사례 전체)로 요약 카드 · 앱 연결 현황 · 장기 무응답을 그리고,
// 안부 연락 처리는 POST /cases/{id}/child-app/welfare-checks 로 저장한다. 화면 값은 src/data/screens/adminApp.ts.
//  - '초대 코드 보내기' 는 담당 상담사만 할 수 있어 준비 중으로 둔다(adminApp.ts 머리말).
//  - '연락 완료로 표시' 는 처리 내용(선택)을 적는 작은 창을 거친다(디자인의 '처리 내용' 칸을 채울 곳).
// 관리자 계정만 본다: 로그인하지 않았으면 로그인 화면으로, 상담원 계정이면 안내만 보인다(훅도 서버를 부르지 않는다).
import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import AdminSidebar, { AdminBlocked } from '../components/AdminSidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { childApp } from '../api/endpoints';
import { useAuthSession } from '../data/useAuthSession';
import { useRemote } from '../data/useRemote';
import { needsLogin } from '../data/screens/common';
import { adminAppValues } from '../data/screens/adminApp';
import '../components/DeleteConfirmDialog.css';
import './Admin.css';

const NOTE_MAX = 200;

function PhaseRow({ t, cols }) {
  if (t.phase === 'rows') return null;
  return (
    <tr>
      <td colSpan={cols} className="note" style={{ textAlign: 'center', padding: '24px 12px' }}>
        {t.phase === 'loading' ? '불러오는 중…' : null}
        {t.phase === 'empty' ? t.emptyText : null}
        {t.phase === 'error' ? (
          <span role="alert">
            {t.errorText}{' '}
            <button type="button" className="btn btn-s btn-sm" onClick={t.retry}>
              다시 시도
            </button>
          </span>
        ) : null}
      </td>
    </tr>
  );
}

function Seg({ label, items }) {
  return (
    <div role="group" aria-label={label} className="seg">
      {items.map((f) => (
        <button key={f.key} type="button" className={f.cls} aria-pressed={f.pressed} onClick={f.pick}>
          {f.label}
        </button>
      ))}
    </div>
  );
}

export default function AdminApp() {
  const session = useAuthSession();
  const theme = useTheme();
  const key = session.status === 'signedIn' && session.isAdmin ? `admin-child-app:${session.me.id}` : null;
  const list = useRemote(
    key,
    () =>
      childApp
        .listCases()
        .then((rows) => ({ off: false, rows }))
        .catch((caught) => {
          if (caught?.code === 'CHILD_APP_DISABLED') return { off: true, rows: [] };
          throw caught;
        }),
    '아이 연계 앱 현황을 불러오지 못했습니다.',
    () => false,
  );
  const [cf, setCf] = useState('all');
  const [sf, setSf] = useState('all');
  const [busy, setBusy] = useState(null);
  const [actError, setActError] = useState('');
  // 연락 완료 창: { caseId, kid, note }
  const [dlg, setDlg] = useState(null);

  const save = async (caseId, status, note) => {
    setBusy(caseId);
    setActError('');
    try {
      await childApp.welfareCheck(caseId, status, note);
      setDlg(null);
      list.refresh();
    } catch (caught) {
      setActError(caught?.message || '안부 연락 처리를 저장하지 못했습니다.');
    } finally {
      setBusy(null);
    }
  };

  const v = adminAppValues({
    rows: list.data ? list.data.rows : null,
    off: Boolean(list.data?.off),
    loading: list.loading,
    error: list.error,
    reload: list.reload,
    cf,
    sf,
    setCf,
    setSf,
    busy,
    openDone: (caseId) => {
      const row = list.data?.rows.find((r) => r.case_id === caseId);
      setActError('');
      setDlg({ caseId, kid: row ? `${row.child_alias} (${row.case_number})` : '', note: '' });
    },
    undo: (caseId) => save(caseId, 'OPEN', null),
  });

  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  if (!session.isAdmin) return <AdminBlocked session={session} />;
  return (
    <div className="pg-Admin pg-AdminApp">
      <div
        className={theme.cls}
        style={{
          minHeight: '1100px',
          background: '#E9E7E1',
          color: '#2B2A26',
          fontFamily: "'IBM Plex Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'stretch',
        }}
      >
        <AdminSidebar active="AdminApp" session={session} />
        <main
          style={{
            flex: '999 1 640px',
            minWidth: '0',
            padding: '30px 36px 56px',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
          }}
        >
          <div className="thm-bar">
            <ThemeToggle />
          </div>
          <header>
            <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>아이 연계 앱 관리</h1>
          </header>
          {actError ? (
            <p className="note" role="alert" style={{ margin: 0, color: '#A33B2E' }}>
              {actError}
            </p>
          ) : null}

          <section
            aria-label="앱 연결 요약"
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}
          >
            <div className="card kpi">
              <span className="sub">전체 아동</span>
              <b>{v.kpis.total}</b>
              <span className="note">진행 중 사례 기준</span>
            </div>
            <div className="card kpi">
              <span className="sub">앱 연결됨</span>
              <b>{v.kpis.on}</b>
              <span className="note">{v.kpis.onNote}</span>
            </div>
            <div className="card kpi">
              <span className="sub">미연결 · 초대 대기</span>
              <b>{v.kpis.notOn}</b>
              <span className="note">{v.kpis.notOnNote}</span>
            </div>
            <a className="card kpi" href="#silent" onClick={(ev) => { ev.preventDefault(); document.getElementById('silent')?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }}>
              <span className="sub acc" style={{ fontWeight: '700' }}>
                장기 무응답 (7일 이상)
              </span>
              <b className="acc">{v.kpis.silent}</b>
              <span className="note">{v.kpis.silentNote}</span>
            </a>
          </section>

          <section className="card" aria-label="앱 연결 현황" style={{ overflow: 'hidden' }}>
            <div className="hd">
              <h2 className="h2">앱 연결 현황</h2>
              <div style={{ marginLeft: 'auto' }}>
                <Seg label="연결 상태" items={v.cFilters} />
              </div>
            </div>
            <div style={{ padding: '18px 22px 4px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div className="stack" role="img" aria-label={v.stack.label}>
                <span style={{ width: v.stack.on, background: '#C2A36B' }}></span>
                <span style={{ width: v.stack.wait, background: '#DAD5C9' }}></span>
                <span style={{ width: v.stack.off, background: '#7A776F' }}></span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 18px' }}>
                {v.stack.legend.map(([color, text]) => (
                  <span key={text} className="lg">
                    <i style={{ background: color }}></i>
                    {text}
                  </span>
                ))}
              </div>
            </div>
            <div style={{ overflowX: 'auto', marginTop: '10px' }}>
              <table className="tbl" style={{ minWidth: '820px' }}>
                <thead>
                  <tr>
                    <th scope="col">아동</th>
                    <th scope="col">담당 상담원</th>
                    <th scope="col">연결 상태</th>
                    <th scope="col">연결일</th>
                    <th scope="col">최근 응답</th>
                    <th scope="col">
                      <span style={{ position: 'absolute', left: '-9999px' }}>작업</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <PhaseRow t={v.conn} cols={6} />
                  {(v.conn.phase === 'rows' ? v.conn.rows : []).map((r) => (
                    <tr key={r.key}>
                      <td>
                        <b style={{ fontWeight: '500' }}>{r.kid}</b>
                        <span className="note" style={{ display: 'block' }}>
                          {r.cid}
                        </span>
                      </td>
                      <td>{r.who}</td>
                      <td>
                        <span className={r.stCls}>{r.st}</span>
                      </td>
                      <td>{r.since}</td>
                      <td>{r.last}</td>
                      <td style={{ textAlign: 'right' }}>
                        {r.canInvite ? (
                          <button
                            type="button"
                            className="btn btn-sm btn-s"
                            disabled
                            title={v.inviteTitle}
                            style={{ opacity: 0.5, cursor: 'not-allowed' }}
                          >
                            {r.invLabel}
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section id="silent" className="card" aria-label="장기 무응답 아동" style={{ overflow: 'hidden' }}>
            <div className="hd">
              <h2 className="h2">장기 무응답 아동</h2>
              <span className="note">마지막 응답 후 7일 이상 · 위험 신호가 아닌 안부 연락 대상</span>
              <div style={{ marginLeft: 'auto' }}>
                <Seg label="안부 연락 처리" items={v.sFilters} />
              </div>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl" style={{ minWidth: '900px' }}>
                <thead>
                  <tr>
                    <th scope="col">아동</th>
                    <th scope="col">담당 상담원</th>
                    <th scope="col">마지막 응답</th>
                    <th scope="col">무응답</th>
                    <th scope="col">안부 연락</th>
                    <th scope="col">처리 내용</th>
                    <th scope="col">
                      <span style={{ position: 'absolute', left: '-9999px' }}>작업</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <PhaseRow t={v.silent} cols={7} />
                  {(v.silent.phase === 'rows' ? v.silent.rows : []).map((r) => (
                    <tr key={r.key}>
                      <td>
                        <b style={{ fontWeight: '500' }}>{r.kid}</b>
                        <span className="note" style={{ display: 'block' }}>
                          {r.cid}
                        </span>
                      </td>
                      <td>{r.who}</td>
                      <td>{r.last}</td>
                      <td>
                        <span className={r.dCls}>{r.days}일</span>
                      </td>
                      <td>
                        <span className={r.stCls}>{r.st}</span>
                      </td>
                      <td className="note" style={{ color: '#2B2A26' }}>
                        {r.memo}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button type="button" className={`btn btn-sm ${r.btnCls}`} onClick={r.toggle} disabled={r.busy}>
                          {r.busy ? '저장 중…' : r.btnLabel}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </main>
      </div>

      {dlg ? (
        <div className="rm-ov" onClick={() => busy === null && setDlg(null)}>
          <div
            className="rm-dlg"
            role="dialog"
            aria-modal="true"
            aria-labelledby="wf-t"
            onClick={(ev) => ev.stopPropagation()}
          >
            <b id="wf-t" style={{ fontSize: '18px' }}>
              안부 연락 완료
            </b>
            <span className="note">{dlg.kid}</span>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span className="sub">처리 내용 (선택)</span>
              <span className="note">관리자도 보는 칸이에요. 연락한 방법 · 결과만 적고, 상담 내용은 적지 마세요.</span>
              <textarea
                className="inp"
                rows={3}
                maxLength={NOTE_MAX}
                placeholder="예: 11/19 통화 · 휴대폰을 같이 써서 응답이 어려움"
                value={dlg.note}
                onChange={(ev) => setDlg({ ...dlg, note: ev.target.value })}
              />
              <span className="note" style={{ textAlign: 'right' }}>
                {dlg.note.length} / {NOTE_MAX}
              </span>
            </label>
            {/* 저장 실패(409 · 네트워크) 문구는 창 안에도 보인다(민규 #185 리뷰 1). */}
            {actError ? (
              <p className="note" role="alert" style={{ margin: 0, color: '#A33B2E' }}>
                {actError}
              </p>
            ) : null}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button type="button" className="btn btn-s btn-sm" onClick={() => setDlg(null)} disabled={busy !== null}>
                취소
              </button>
              <button
                type="button"
                className="btn btn-p btn-sm"
                onClick={() => save(dlg.caseId, 'DONE', dlg.note)}
                disabled={busy !== null}
              >
                {busy ? '저장 중…' : '연락 완료로 표시'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
