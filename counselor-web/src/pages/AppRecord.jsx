// 상담사 앱(폰) · 녹음
// 원본: 앱 · 녹음 (아이 · 회차 선택 → 녹음 → 저장하고 올리기 · 업로드 실패 알림) 2026-11-10 zip 의 AppRecord.dc.html
//
// 서버 연결
//  - 아이: 내 진행 중 사례(useAppCases). 이름은 실명, 없으면 별칭. 연결이 없으면 이 폰에 기억한 목록으로 고른다.
//    연결이 없을 때 회차는 '새 회차' 만 고를 수 있다(회차 목록을 못 불러옴). 녹음은 폰에 저장했다가 연결되면 올린다.
//  - 회차: 고른 사례의 회차 중 녹음을 올릴 수 있는 것(빈 회차 · 녹음만 있는 회차 · 변환 실패 회차) + '새 회차'.
//    '새 회차' 면 올릴 때 회차를 만든다(상담 일시 = 녹음 시작 시각, 상담 유형 = 고른 값).
//  - 저장하고 올리기: 녹음을 폰(IndexedDB)에 저장한 뒤 회차 만들기 → 음성 올리기 → 원문 변환 요청(appRecordings.ts).
//    웹에서 같은 사례 · 회차를 열면 녹음이 있고, 변환이 끝나면 1단계(원문 검수)부터 이어서 한다.
//  - 주소에 ?case=<사례 ID> 가 있으면 그 아이를 골라 둔다(앱 사례 목록 · 브리핑의 '녹음' 단추용).
// 디자인과 다른 점
//  - 상담 유형 4개는 디자인 그대로(정기 · 방문 · 전화 · 기관 면담). 서버 값으로 바꿔 보낸다.
//  - '화면을 닫아도 계속 올려요' 는 웹 앱이라 그대로 지킬 수 없어 '화면을 닫으면 다음에 열 때 이어서 올려요' 로 적었다.
//  - 맨 아래 시안 안내 문구는 실제 동작 안내로 바꿨다.
import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import MobileAppShell from '../components/MobileAppShell';
import { cases } from '../api/endpoints';
import { childLabelOf, useAppCases } from '../data/useAppCases';
import { fileNameFor, finishDraft } from '../data/appRecordings';
import { kindLabel } from '../data/useAppRecordings';
import {
  clearRecording,
  preloadRecorder,
  pauseRecording,
  resetRecording,
  resumeRecording,
  setRecorderError,
  startRecording,
  stopRecording,
  useRecorder,
} from '../data/useRecorder';

const KINDS = [
  ['REGULAR', '정기상담'],
  ['VISIT', '방문상담'],
  ['PHONE', '전화상담'],
  ['OFFICE', '기관 면담'],
];
const UPLOADABLE = new Set(['CREATED', 'AUDIO_UPLOADED', 'STT_FAILED']);
const ST = { idle: '녹음 대기', rec: '녹음 중', paused: '일시정지', done: '녹음 완료', saved: '저장 완료' };

function mmss(ms) {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  return h > 0 ? `${h}:${m}:${ss}` : `${m}:${ss}`;
}

function useUploadableSessions(caseId) {
  const [state, setState] = useState({ caseId: null, rows: [] });
  useEffect(() => {
    if (!caseId) return undefined;
    let live = true;
    cases
      .listSessions(caseId, { page: 1, page_size: 100 })
      .then((page) => {
        if (!live) return;
        const rows = page.items
          .filter((row) => UPLOADABLE.has(row.status) && row.source !== 'DOCUMENT')
          .sort((a, b) => b.session_number - a.session_number);
        setState({ caseId, rows });
      })
      .catch(() => live && setState({ caseId, rows: [] }));
    return () => {
      live = false;
    };
  }, [caseId]);
  return state.caseId === caseId ? state.rows : [];
}

function RecordBody({ userId, items, loaded }) {
  const rec = useRecorder();
  // MP3 변환 도구를 미리 받아 둔다(녹음 시작을 누른 순간 기다리지 않게 · 연결 없을 때도 쓰게).
  useEffect(() => preloadRecorder(), []);
  const [params] = useSearchParams();
  const my = useAppCases(userId);
  const [caseId, setCaseId] = useState(null);
  const [ses, setSes] = useState('new');
  const [kind, setKind] = useState('REGULAR');
  const [con, setCon] = useState(false);
  const [err, setErr] = useState(false);
  const [savedId, setSavedId] = useState(null);
  const [saving, setSaving] = useState(false);

  // 녹음 중에 다른 탭에 다녀오면 녹음 중인 아이 · 회차 · 유형을 그대로 보인다.
  const draft = rec.draft;
  const selCase = draft ? draft.caseId : caseId;
  const selSes = draft ? draft.sessionId ?? 'new' : ses;
  const selKind = draft ? draft.consultationType : kind;

  useEffect(() => {
    if (caseId || my.rows.length === 0) return;
    const want = params.get('case');
    setCaseId(my.rows.some((row) => row.id === want) ? want : my.rows[0].id);
  }, [my.rows, caseId, params]);

  const sessionRows = useUploadableSessions(selCase);
  const child = my.rows.find((row) => row.id === selCase);
  const childLabel = draft ? draft.childLabel : child ? childLabelOf(child) : '';
  const session = sessionRows.find((row) => row.id === selSes);
  const sesLabel = selSes === 'new' ? '새 회차' : session ? session.session_number + '회차' : draft?.sessionNumber ? draft.sessionNumber + '회차' : '';
  const kindText = KINDS.find(([k]) => k === selKind)?.[1] ?? kindLabel(selKind);

  const phase = savedId && rec.phase === 'idle' ? 'saved' : rec.phase;
  const lock = phase !== 'idle' || saving;
  const savedItem = savedId ? items.find((x) => x.id === savedId) : null;
  const qs = savedItem ? (savedItem.status === 'wait' ? 'run' : savedItem.status) : loaded && savedId ? 'done' : 'run';

  const fails = useMemo(() => items.filter((x) => x.status === 'fail'), [items]);

  const start = async () => {
    if (!con) {
      setErr(true);
      return;
    }
    if (!child || !userId) return;
    // 녹음이 있는 회차를 고르면 바꿀지 한 번 묻는다(폰에서는 잘못 고르기 쉬워서, 민규 #168).
    if (session && session.status !== 'CREATED' && !window.confirm('이 회차에는 이미 녹음이 있어요. 바꿀까요?')) return;
    setSavedId(null);
    await startRecording({
      userId,
      caseId: child.id,
      childLabel,
      sessionId: ses === 'new' ? null : ses,
      sessionNumber: session ? session.session_number : null,
      expectStatus: session ? session.status : 'CREATED',
      consultationType: kind,
      consultedAt: new Date().toISOString(),
    });
  };

  const save = async () => {
    if (!draft || saving) return;
    setSaving(true);
    try {
      const name = fileNameFor(draft, kindText);
      const id = await finishDraft(draft, name, rec.elapsedMs);
      clearRecording();
      setSavedId(id);
      setCon(false);
    } catch {
      setRecorderError('폰에 녹음을 저장하지 못했어요. 저장 공간을 확인한 뒤 다시 눌러 주세요.');
    } finally {
      setSaving(false);
    }
  };

  const reset = () => {
    if (phase === 'saved') {
      setSavedId(null);
      setCon(false);
      return;
    }
    resetRecording();
    setCon(false);
  };

  return (
    <>
      {fails.length > 0 && (
        <Link className="ma-fail" to="/AppUpload">
          <span>{'업로드 실패 ' + fails.length + '건 · 다시 올려 주세요'}</span>보기 ›
        </Link>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
        <label className="ma-fl">
          <span className="ma-lb">아이</span>
          <select
            className="ma-inp"
            value={selCase ?? ''}
            onChange={(ev) => {
              setCaseId(ev.target.value);
              setSes('new');
            }}
            disabled={lock || my.loading || my.rows.length === 0}
          >
            {my.loading && <option value="">불러오는 중</option>}
            {!my.loading && my.rows.length === 0 && <option value="">담당 사례 없음</option>}
            {draft && !child && <option value={draft.caseId}>{draft.childLabel}</option>}
            {my.rows.map((row) => (
              <option key={row.id} value={row.id}>
                {childLabelOf(row)}
              </option>
            ))}
          </select>
        </label>
        <label className="ma-fl">
          <span className="ma-lb">회차</span>
          <select className="ma-inp" value={selSes} onChange={(ev) => setSes(ev.target.value)} disabled={lock}>
            <option value="new">새 회차</option>
            {draft && draft.sessionId && !session && <option value={draft.sessionId}>{sesLabel}</option>}
            {sessionRows.map((row) => (
              <option key={row.id} value={row.id}>
                {row.session_number + '회차' + (row.status === 'CREATED' ? '' : ' · 녹음 바꾸기')}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="ma-fl">
        <span className="ma-lb">상담 유형</span>
        <select className="ma-inp" value={selKind} onChange={(ev) => setKind(ev.target.value)} disabled={lock}>
          {KINDS.map(([k, label]) => (
            <option key={k} value={k}>
              {label}
            </option>
          ))}
        </select>
      </label>
      {my.error && <span className="ma-err">{my.error}</span>}
      <section className="ma-card ma-rbox" aria-label="녹음">
        <span className="ma-rstat">
          <span className={phase === 'rec' ? 'ma-rdot ma-live' : 'ma-rdot'}></span>
          {ST[phase]}
        </span>
        <span className="ma-rtime" aria-live="polite">
          {mmss(phase === 'saved' ? savedItem?.durationMs ?? 0 : rec.elapsedMs)}
        </span>
        {rec.error && <span className="ma-err">{rec.error}</span>}
        {phase === 'idle' && (
          <>
            <label className="ma-con">
              <input
                type="checkbox"
                checked={con}
                onChange={(ev) => {
                  setCon(!!ev.target.checked);
                  setErr(false);
                }}
              />
              <span>녹음 동의 완료</span>
            </label>
            {err && <span className="ma-err">녹음 동의를 먼저 확인해 주세요</span>}
            <button type="button" className="ma-rbig" onClick={start} aria-label="녹음 시작" disabled={!child}>
              <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"></rect><path d="M5 11a7 7 0 0 0 14 0M12 18v3"></path></svg>
            </button>
          </>
        )}
        {(phase === 'rec' || phase === 'paused') && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <button type="button" className="ma-btn" onClick={phase === 'paused' ? resumeRecording : pauseRecording}>
              {phase === 'paused' ? '계속' : '일시정지'}
            </button>
            <button type="button" className="ma-rbig ma-stop" onClick={() => void stopRecording()} aria-label="녹음 정지">
              ■ 정지
            </button>
          </div>
        )}
        {phase === 'done' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '8px', width: '100%' }}>
            <button type="button" className="ma-btn" onClick={reset} disabled={saving}>
              다시 녹음
            </button>
            <button type="button" className="ma-btn ma-btn-p" onClick={save} disabled={saving}>
              저장하고 올리기
            </button>
          </div>
        )}
        {phase === 'saved' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', width: '100%', textAlign: 'left' }}>
            <b>{savedItem ? `${savedItem.childLabel} · ${savedItem.sessionNumber ? savedItem.sessionNumber + '회차' : '새 회차'} · ${kindLabel(savedItem.consultationType)} · ${mmss(savedItem.durationMs)}` : ''}</b>
            {qs === 'run' && (
              <>
                <span className="ma-note">업로드 중이에요. 화면을 닫으면 다음에 열 때 이어서 올려요.</span>
                <div className="ma-prog">
                  <span></span>
                </div>
              </>
            )}
            {qs === 'done' && <span style={{ fontWeight: 700 }}>✓ 업로드 완료</span>}
            {qs === 'fail' && (
              <span className="ma-err">{savedItem?.needNewSession ? savedItem.error : '업로드 실패 · 연결이 돌아오면 다시 올려 주세요'}</span>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              <Link className="ma-btn" to="/AppUpload">
                업로드 목록
              </Link>
              <button type="button" className="ma-btn ma-btn-p" onClick={reset}>
                새 녹음
              </button>
            </div>
          </div>
        )}
      </section>
      <p className="ma-note" style={{ margin: 0 }}>
        녹음하는 동안에는 화면을 켜 두세요. 전화 · 화면 꺼짐으로 마이크가 끊기면 일시정지되고, 돌아와 '계속' 을 누르면 같은 녹음에 이어서 녹음해요(끊긴 동안은 녹음되지 않아요). 녹음은 이 휴대폰에 먼저 저장한 뒤 올려요. 연결이 끊기면 다시 연결될 때 자동으로 다시 올려요. 올린 녹음은 웹의 같은 사례 · 회차에서
        이어서 확인할 수 있어요.
      </p>
    </>
  );
}

export default function AppRecord() {
  return (
    <MobileAppShell cur="rec" sub="현장 상담 녹음" title="녹음">
      {(ctx) => <RecordBody {...ctx} />}
    </MobileAppShell>
  );
}
