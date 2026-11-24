// 상담사 앱(폰) · 사례 목록
// 원본: 앱 · 사례 목록 (찾기 · 이번 주 상담 → 사례 요약 · 브리핑 · 녹음) 2026-11-10 zip 의 AppCases.dc.html
//
// 서버 연결
//  - 목록: 내 진행 중 사례(useAppCases — GET /cases?status=ACTIVE&with_child_name=true). 이름은 실명, 없으면 별칭.
//    나이는 출생 연도로, 신고접수는 report_date, 위험도는 웹 사례 목록과 같이 분석이 끝난 최근 회차의 상담원 판단 →
//    없으면 위험도(우선)(counselor_risk_level), 둘 다 없으면 '—'.
//  - 다음 상담: 오늘부터 4주 안 일정 중 그 사례의 가장 가까운 상담(GET /schedule/events). '이번 주 상담' 은 다음 상담이 이번 주(월~일)인 사례.
//  - 찾기: 이름 · 별칭 · 사례 ID 에 들어 있으면(이 폰에서 거름).
//  - 사례 요약 창(11/17 디자인 '각진 UI ⑨' — 가운데 창): 사례 ID · 신고접수 · 다음 상담 · 메모(이 아이에 대해 쓴 내 메모,
//    GET /memos?case_id= 최신 MEMO_N 개 — 본문은 화면에만, 폰에 저장하지 않음). 단추는 디자인 순서대로 다음 상담 준비(앱 · 브리핑) ·
//    자료 올리기(앱 · 업로드) · 이전 상담(앱 · 이전 상담)이고, 그 아이를 골라 둔 채 간다(?case=). 녹음 · 메모는 아래 탭에서 한다(디자인).
//    디자인의 '다음 상담 준비중' 은 준비 여부를 정할 서버 값이 없어 늘 '다음 상담 준비' 를 보이고, 그 화면이 빈 칸을 안내한다.
//  - 11/19 디자인: 사례 요약 단추에 '메모 추가 / 메모 수정'(그 아이 메모가 있으면 수정). 앱 메모와 같은 서버 메모 API 를 쓴다.
//    추가: 작성 · 취소 · 확인 → POST /memos(case_id = 이 사례). 수정: 그 아이의 가장 최근 메모를 열어 삭제 · 취소 · 수정 →
//    PATCH /memos/{id}(본문만) · DELETE /memos/{id}('메모를 삭제하시겠습니까?' 확인). 저장하면 요약의 메모 칸을 다시 부른다.
//    서버가 거절하면(연결 없음 등) 창 안에 오류를 보이고 적은 글은 그대로 둔다(디자인에 없는 줄).
//  - 걸러 보기를 바꾸면 카드가 차례로 올라오고, 창은 열고 닫을 때 움직인다(MobileAppShellMotion, 동작 줄이기면 끔).
//  - 연결이 없으면 기억한 목록(이름만)이라 나이 · 위험도 · 신고접수는 '—'.
//  - 11/20 디자인: '전체 / 이번 주 상담' 아래 '+ 새 사례 등록' → 가운데 창(아동 이름 · 생년월일 · 성별, 셋 다 채워야 '등록').
//    POST /cases 로 서버에 만든다(보낼 값은 appCaseRegister.ts — 웹 등록과 같은 함수, 실명 · 생년월일은 personal_info 로 암호화 저장,
//    성별 · 출생연도는 사례 칸). 성공하면 '전체' · 찾기 비움으로 돌리고 사례 목록을 다시 부른다(서버 기본 순서가 등록 최신순이라 맨 위).
//    서버가 거절하면 창 안 오류 줄에 보이고 적은 값은 그대로 둔다. 하단 '사례 등록과 자세한 기록은 웹에서…' 문구는 디자인대로 뺐다.
//  - 사례 요약의 생년월일 · 성별 줄(11/20 디자인): 성별은 사례의 child_gender, 생년월일은 실명 정보 창구
//    (GET /cases/{id}/personal-info — 부를 때마다 서버에 열람 기록이 남는다). 그래서 요약 창을 열 때만, 출생연도가 있는 사례
//    (생년월일이 저장됐을 수 있는 사례)만 부른다. 둘 다 없으면 줄을 보이지 않는다(디자인: 생년월일이 있는 사례만).
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import MobileAppShell, { whenText } from '../components/MobileAppShell';
import { RISK_LEVEL_LABELS, SCHEDULE_CONSULT_LABELS } from '../api/types';
import { cases as caseApi, memos as memoApi } from '../api/endpoints';
import { parseBackendTime } from '../data/time';
import { closeWithAnim, staggerIn } from '../components/MobileAppShellMotion';
import { errorMessage, useRemote } from '../data/useRemote';
import { childLabelOf, reloadAppCases, useAppCases } from '../data/useAppCases';
import {
  APP_CASE_NAME_MAX,
  APP_CASE_SEXES,
  BIRTH_FORMAT_ERROR,
  REGISTER_MISSING_ERROR,
  appRegisterReady,
  nextBirthValue,
  toAppCaseCreateRequest,
} from '../data/appCaseRegister';
import { addDays, mondayOf, parseYmd, useAppSchedule, ymd } from '../data/useAppSchedule';

const W = ['일', '월', '화', '수', '목', '금', '토'];
/** 사례 요약 창에 보일 그 아이 메모 수(최신순). 더 있으면 '외 N개 · 메모 탭에서'. */
const MEMO_N = 3;
const RC = { 상: 'ma-chip ma-red', 중: 'ma-chip ma-gold', 하: 'ma-chip' };

export function consultText(e) {
  const d = parseYmd(e.date);
  const type = e.consult_type ? SCHEDULE_CONSULT_LABELS[e.consult_type] : '상담';
  return `${d.getMonth() + 1}/${d.getDate()}(${W[d.getDay()]})${e.time ? ' ' + e.time : ''} · ${type}`;
}

function CasesBody({ userId }) {
  const my = useAppCases(userId);
  const now = new Date();
  const sched = useAppSchedule(!!userId, ymd(now), ymd(addDays(now, 27)));
  const weekEnd = ymd(addDays(mondayOf(now), 6));
  const [q, setQ] = useState('');
  const [f, setF] = useState('all');
  const [open, setOpen] = useState(null);
  // 메모 추가 · 수정 창: { mode: 'add' | 'edit', id, text }. ask = 삭제 확인 창.
  const [mm, setMm] = useState(null);
  const [mmAsk, setMmAsk] = useState(false);
  const [mmErr, setMmErr] = useState('');
  const [busy, setBusy] = useState(false);
  const shRef = useRef(null);
  const mmRef = useRef(null);
  const askRef = useRef(null);
  const firstF = useRef(true);
  // 새 사례 등록 창: { name, birth, sex, err }. 닫혀 있으면 null.
  const [rg, setRg] = useState(null);
  const [rgBusy, setRgBusy] = useState(false);
  const rgRef = useRef(null);
  const memo = useRemote(
    open ? `app-case-memo:${open}` : null,
    () => memoApi.list({ case_id: open, page: 1, page_size: MEMO_N }),
    '메모를 불러오지 못했습니다.',
    () => false,
  );
  // 사례 요약의 생년월일(실명 정보 창구 — 열람 기록이 남아 요약을 열 때 · 출생연도가 있는 사례만 부른다).
  const openRow = open ? my.rows.find((r) => r.id === open) : null;
  const pi = useRemote(
    open && openRow?.child_birth_year ? `app-case-pi:${open}` : null,
    () => caseApi.getPersonalInfo(open),
    '생년월일을 불러오지 못했습니다.',
    () => false,
  );

  // 걸러 보기를 바꾸면 카드를 차례로 올린다(디자인 CH.f).
  useEffect(() => {
    if (firstF.current) {
      firstF.current = false;
      return;
    }
    staggerIn('.ma-amain .ma-card.ma-cs, .ma-amain .ma-card.ma-empty');
  }, [f]);

  const nextOf = (caseId) => sched.items.find((e) => e.kind === 'CONSULT' && e.case_id === caseId) ?? null;
  const rows = my.rows.map((r) => {
    const level = r.risk_level ?? r.counselor_risk_level ?? null;
    const rk = level ? RISK_LEVEL_LABELS[level] : '—';
    const next = nextOf(r.id);
    return {
      r,
      name: childLabelOf(r),
      id: r.case_number ?? '—',
      age: r.child_birth_year ? `${now.getFullYear() - r.child_birth_year}세` : '',
      date: r.report_date ?? '—',
      rk,
      rkCls: RC[rk] ?? 'ma-chip',
      next,
    };
  });
  const term = q.trim().toLowerCase();
  const list = rows.filter(
    (x) =>
      (f === 'wk' ? !!x.next && x.next.date <= weekEnd : true) &&
      (!term ||
        x.name.toLowerCase().includes(term) ||
        (x.r.child_alias ?? '').toLowerCase().includes(term) ||
        x.id.toLowerCase().includes(term)),
  );
  const cur = open ? rows.find((x) => x.r.id === open) : null;
  const stop = (ev) => ev.stopPropagation();
  const myM = memo.data?.items ?? [];
  const memoReady = !!memo.data && !memo.error;
  const shClose = () => closeWithAnim(shRef.current, () => setOpen(null));
  const mmCancel = () =>
    closeWithAnim(mmRef.current, () => {
      setMm(null);
      setMmAsk(false);
      setMmErr('');
    });
  const mmOpen = () => {
    setMmErr('');
    setMmAsk(false);
    setMm(myM.length ? { mode: 'edit', id: myM[0].id, text: myM[0].text ?? '' } : { mode: 'add', id: '', text: '' });
  };
  // 서버에 쓰고 성공하면 요약의 메모 칸을 다시 부르고 창을 닫는다. 실패하면 창에 오류를 두고 글은 그대로.
  const mmRun = async (work, failText, closeEls) => {
    if (busy) return;
    setBusy(true);
    setMmErr('');
    try {
      await work();
      memo.refresh();
      closeEls.slice(1).forEach((el) => el && closeWithAnim(el, () => {}));
      closeWithAnim(closeEls[0], () => {
        setMm(null);
        setMmAsk(false);
      });
    } catch (caught) {
      setMmErr(errorMessage(caught, failText));
    } finally {
      setBusy(false);
    }
  };
  const mmSaveAdd = () => {
    const text = (mm?.text || '').trim();
    if (!text || !cur) return;
    void mmRun(() => memoApi.create({ text, case_id: cur.r.id }), '메모를 저장하지 못했습니다. 연결을 확인해 주십시오.', [mmRef.current]);
  };
  const mmSaveEdit = () => {
    const text = (mm?.text || '').trim();
    if (!text) return;
    void mmRun(() => memoApi.update(mm.id, { text }), '메모를 수정하지 못했습니다. 연결을 확인해 주십시오.', [mmRef.current]);
  };
  const mmDel = () => {
    // 지우면 확인 창과 메모 창을 함께 닫는다.
    void mmRun(() => memoApi.remove(mm.id), '메모를 삭제하지 못했습니다. 연결을 확인해 주십시오.', [askRef.current, mmRef.current]);
  };
  const rgCancel = () => closeWithAnim(rgRef.current, () => setRg(null));
  const rgSave = async () => {
    if (!rg || rgBusy) return;
    if (!appRegisterReady(rg)) {
      setRg({ ...rg, err: REGISTER_MISSING_ERROR });
      return;
    }
    const checked = toAppCaseCreateRequest(rg, userId);
    if (checked.problem !== null) {
      setRg({ ...rg, err: checked.problem });
      return;
    }
    setRgBusy(true);
    try {
      await caseApi.create(checked.payload);
      reloadAppCases();
      closeWithAnim(rgRef.current, () => setRg(null));
      setF('all');
      setQ('');
    } catch (caught) {
      setRg((cur0) => cur0 && { ...cur0, err: errorMessage(caught, '사례를 등록하지 못했습니다. 연결을 확인해 주십시오.') });
    } finally {
      setRgBusy(false);
    }
  };
  const setRgBirth = (ev) => {
    const el = ev.target;
    const next = nextBirthValue(el.value);
    const prev = rg?.birth ?? '';
    if (!next.ok) {
      el.value = prev;
      setRg({ ...rg, birth: prev, err: BIRTH_FORMAT_ERROR });
      return;
    }
    setRg({ ...rg, birth: next.value, err: '' });
  };
  const birthOf = () => {
    if (!cur?.r.child_birth_year) return '';
    if (pi.loading && !pi.data) return '불러오는 중';
    return pi.data?.child_birth_date ?? '';
  };
  const birth = birthOf();
  const sex = cur?.r.child_gender ?? '';
  const F = [
    ['all', '전체'],
    ['wk', '이번 주 상담'],
  ];

  return (
    <>
      <input className="ma-inp" type="search" placeholder="이름 또는 사례 ID로 찾기" aria-label="사례 찾기" value={q} onChange={(ev) => setQ(ev.target.value)} />
      <div className="ma-seg" role="radiogroup" aria-label="사례 걸러 보기">
        {F.map(([k, label]) => (
          <button key={k} type="button" role="radio" aria-checked={f === k ? 'true' : 'false'} className={f === k ? 'ma-on' : ''} onClick={() => setF(k)}>
            {label}
          </button>
        ))}
      </div>
      <button type="button" className="ma-btn ma-btn-block ma-reg-btn" onClick={() => setRg({ name: '', birth: '', sex: '', err: '' })}>
        <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14"></path></svg>새 사례 등록
      </button>
      <p className="ma-sec-t">{my.loading ? '불러오는 중' : list.length + '명'}</p>
      {(my.error || sched.error) && <span className="ma-err">{my.error || sched.error}</span>}
      {list.map((x) => (
        <div
          key={x.r.id}
          className="ma-card ma-cs"
          role="button"
          tabIndex={0}
          aria-label={x.name + ' 사례 요약 보기'}
          onClick={() => setOpen(x.r.id)}
          onKeyDown={(ev) => (ev.key === 'Enter' || ev.key === ' ') && setOpen(x.r.id)}
        >
          <div className="ma-cs-top">
            <b>{x.name}</b>
            <span className="ma-note">{x.age}</span>
            <span className={x.rkCls} style={{ marginLeft: 'auto' }}>
              위험도 {x.rk}
            </span>
          </div>
          <span className="ma-note">
            {x.id} · 신고접수 {x.date}
          </span>
          <span className={x.next ? 'ma-cs-next' : 'ma-cs-next ma-none'}>
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"></rect><path d="M16 3v4M8 3v4M3 10h18"></path></svg>
            {x.next ? '다음 상담 ' + consultText(x.next) : '예정된 상담 없음'}
          </span>
        </div>
      ))}
      {!my.loading && list.length === 0 && <div className="ma-card ma-empty">찾는 사례가 없습니다</div>}
      {cur && (
        <div className="ma-ov ma-ov-c" ref={shRef} onClick={shClose}>
          <section className="ma-sheet ma-sheet-c" role="dialog" aria-modal="true" aria-label="사례 요약" onClick={stop}>
            <div className="ma-sh-hd">
              <b>{cur.name + (cur.age ? ' · ' + cur.age : '')}</b>
              <span className={cur.rkCls}>위험도 {cur.rk}</span>
            </div>
            <div>
              {[
                ['사례 ID', cur.id, ''],
                ...(birth || sex
                  ? [
                      ['생년월일', birth || '—', ''],
                      ['성별', sex || '—', ''],
                    ]
                  : []),
                ['신고접수', cur.date, ''],
                ['다음 상담', cur.next ? consultText(cur.next) : '예정 없음', ''],
                ['메모', <CaseMemo key="memo" memo={memo} />, 'ma-kv-memo'],
              ].map(([k, v, cls]) => (
                <div key={k} className="ma-row-k">
                  <span>{k}</span>
                  <span className={cls}>{v}</span>
                </div>
              ))}
            </div>
            <div className="ma-acts">
              <Link className="ma-btn" to={`/AppBrief?case=${cur.r.id}`} state={{ from: '/AppCases' }}>
                다음 상담 준비
              </Link>
              <Link className="ma-btn" to={`/AppUpload?case=${cur.r.id}`}>
                자료 올리기
              </Link>
              <Link className="ma-btn" to={`/AppHistory?case=${cur.r.id}`} state={{ from: '/AppCases' }}>
                이전 상담
              </Link>
              <button type="button" className="ma-btn" onClick={mmOpen} disabled={!memoReady}>
                {myM.length ? '메모 수정' : '메모 추가'}
              </button>
            </div>
          </section>
        </div>
      )}
      {cur && mm && (
        <div className="ma-ov ma-ov-c ma-ov-mm" ref={mmRef} onClick={mmCancel}>
          <section className="ma-sheet ma-sheet-c" role="dialog" aria-modal="true" aria-label={mm.mode === 'edit' ? '메모 수정' : '메모 추가'} onClick={stop}>
            <div className="ma-sh-hd">
              <b>{mm.mode === 'edit' ? '메모 수정' : '메모 추가'}</b>
              <span className="ma-note">{cur.name}</span>
            </div>
            <textarea
              className="ma-inp"
              rows={5}
              placeholder="메모를 입력하십시오"
              value={mm.text}
              onChange={(ev) => setMm({ ...mm, text: ev.target.value })}
              aria-label="메모 내용"
              maxLength={4000}
            />
            {mmErr && !mmAsk && <span className="ma-err">{mmErr}</span>}
            {mm.mode === 'add' ? (
              <div className="ma-mm-acts">
                <button type="button" className="ma-btn" onClick={mmCancel}>
                  취소
                </button>
                <button type="button" className="ma-btn ma-btn-p" onClick={mmSaveAdd} disabled={busy}>
                  확인
                </button>
              </div>
            ) : (
              <div className="ma-mm-acts ma-mm-3">
                <button type="button" className="ma-btn ma-btn-red" onClick={() => setMmAsk(true)}>
                  삭제
                </button>
                <button type="button" className="ma-btn" onClick={mmCancel}>
                  취소
                </button>
                <button type="button" className="ma-btn ma-btn-p" onClick={mmSaveEdit} disabled={busy}>
                  수정
                </button>
              </div>
            )}
          </section>
        </div>
      )}
      {cur && mm && mmAsk && (
        <div className="ma-ov ma-ov-c ma-ov-ask" ref={askRef} onClick={() => closeWithAnim(askRef.current, () => setMmAsk(false))}>
          <section className="ma-sheet ma-sheet-c" role="alertdialog" aria-modal="true" aria-label="메모 삭제 확인" onClick={stop}>
            <b className="ma-mm-q">메모를 삭제하시겠습니까?</b>
            {mmErr && <span className="ma-err">{mmErr}</span>}
            <div className="ma-mm-acts">
              <button type="button" className="ma-btn" onClick={() => closeWithAnim(askRef.current, () => setMmAsk(false))}>
                취소
              </button>
              <button type="button" className="ma-btn ma-mm-del" onClick={mmDel} disabled={busy}>
                삭제
              </button>
            </div>
          </section>
        </div>
      )}
      {rg && (
        <div className="ma-ov ma-ov-c ma-ov-reg" ref={rgRef} onClick={rgCancel}>
          <section className="ma-sheet ma-sheet-c" role="dialog" aria-modal="true" aria-label="새 사례 등록" onClick={stop}>
            <div className="ma-sh-hd">
              <b>새 사례 등록</b>
            </div>
            <label className="ma-rg-f">
              <span>아동 이름</span>
              <input
                className="ma-inp"
                type="text"
                placeholder="이름을 입력하십시오"
                value={rg.name}
                onChange={(ev) => setRg({ ...rg, name: ev.target.value.slice(0, APP_CASE_NAME_MAX), err: '' })}
                aria-label="아동 이름"
              />
            </label>
            <label className="ma-rg-f">
              <span>생년월일</span>
              <input
                className="ma-inp"
                type="text"
                inputMode="numeric"
                autoComplete="off"
                placeholder="YYYY-MM-DD"
                value={rg.birth}
                onChange={setRgBirth}
                aria-label="생년월일 (YYYY-MM-DD)"
              />
            </label>
            <div className="ma-rg-f">
              <span>성별</span>
              <div className="ma-seg" role="radiogroup" aria-label="성별">
                {APP_CASE_SEXES.map((g) => (
                  <button
                    key={g}
                    type="button"
                    role="radio"
                    aria-checked={rg.sex === g ? 'true' : 'false'}
                    className={rg.sex === g ? 'ma-on' : ''}
                    onClick={() => setRg({ ...rg, sex: g, err: '' })}
                  >
                    {g}
                  </button>
                ))}
              </div>
            </div>
            {rg.err && (
              <p className="ma-rg-err" role="alert">
                {rg.err}
              </p>
            )}
            <div className="ma-mm-acts">
              <button type="button" className="ma-btn" onClick={rgCancel}>
                취소
              </button>
              <button type="button" className="ma-btn ma-btn-p" disabled={!appRegisterReady(rg) || rgBusy} onClick={rgSave}>
                등록
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  );
}

/** 사례 요약 창의 '메모' 칸: 그 아이에 대해 쓴 내 메모 최신 MEMO_N 개('본문 (시각)'), 없으면 '-'. memo = 위 useRemote. */
function CaseMemo({ memo }) {
  if (memo.loading && !memo.data) return '불러오는 중';
  if (memo.error) return memo.error;
  const items = memo.data?.items ?? [];
  if (items.length === 0) return '-';
  const more = (memo.data?.meta?.total ?? items.length) - items.length;
  const at = (iso) => whenText(parseBackendTime(iso)?.getTime() ?? Date.now());
  const text = items
    .map((m) => (m.unreadable ? '지금은 읽을 수 없는 메모' : m.text) + ' (' + at(m.updated_at) + ')')
    .join('\n\n');
  return more > 0 ? `${text}\n\n외 ${more}개 · 메모 탭에서 볼 수 있습니다` : text;
}

function CaseCount({ userId }) {
  const my = useAppCases(userId);
  return my.loading ? '담당 —' : `담당 ${my.rows.length}명`;
}

export default function AppCases() {
  return (
    <MobileAppShell cur="cases" screen="cases" sub={({ userId }) => <CaseCount userId={userId} />} title="사례 목록">
      {(ctx) => <CasesBody {...ctx} />}
    </MobileAppShell>
  );
}
