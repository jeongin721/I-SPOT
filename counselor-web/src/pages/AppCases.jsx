// 상담사 앱(폰) · 사례 목록
// 원본: 앱 · 사례 목록 (찾기 · 이번 주 상담 → 사례 요약 · 브리핑 · 녹음) 2026-11-10 zip 의 AppCases.dc.html
//
// 서버 연결
//  - 목록: 내 진행 중 사례(useAppCases — GET /cases?status=ACTIVE&with_child_name=true). 이름은 실명, 없으면 별칭.
//    나이는 출생 연도로, 신고접수는 report_date, 위험도는 웹 사례 목록과 같이 분석이 끝난 최근 회차의 상담원 판단 →
//    없으면 위험도(우선)(counselor_risk_level), 둘 다 없으면 '—'.
//  - 다음 상담: 오늘부터 4주 안 일정 중 그 사례의 가장 가까운 상담(GET /schedule/events). '이번 주 상담' 은 다음 상담이 이번 주(월~일)인 사례.
//  - 찾기: 이름 · 별칭 · 사례 ID 에 들어 있으면(이 폰에서 거름).
//  - 사례 요약 창: 상담 전 브리핑(앱 · 브리핑) · 녹음 시작 · 자료 올리기 · 메모로 그 아이를 골라 둔 채 간다(?case=).
//    디자인의 '브리핑 준비 중' 은 준비 여부를 정할 서버 값이 없어 늘 '상담 전 브리핑' 을 보이고, 브리핑 화면이 빈 칸을 안내한다.
//  - 연결이 없으면 기억한 목록(이름만)이라 나이 · 위험도 · 신고접수는 '—'.
import { useState } from 'react';
import { Link } from 'react-router-dom';
import MobileAppShell from '../components/MobileAppShell';
import { RISK_LEVEL_LABELS, SCHEDULE_CONSULT_LABELS } from '../api/types';
import { childLabelOf, useAppCases } from '../data/useAppCases';
import { addDays, mondayOf, parseYmd, useAppSchedule, ymd } from '../data/useAppSchedule';

const W = ['일', '월', '화', '수', '목', '금', '토'];
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
      {!my.loading && list.length === 0 && <div className="ma-card ma-empty">찾는 사례가 없어요</div>}
      <p className="ma-note" style={{ margin: 0 }}>
        사례 등록과 자세한 기록은 웹에서 할 수 있어요.
      </p>
      {cur && (
        <div className="ma-ov" onClick={() => setOpen(null)}>
          <section className="ma-sheet" role="dialog" aria-modal="true" aria-label="사례 요약" onClick={stop}>
            <span className="ma-grab" aria-hidden="true"></span>
            <div className="ma-sh-hd">
              <b>{cur.name + (cur.age ? ' · ' + cur.age : '')}</b>
              <span className={cur.rkCls}>위험도 {cur.rk}</span>
            </div>
            <div>
              {[
                ['사례 ID', cur.id],
                ['신고접수', cur.date],
                ['다음 상담', cur.next ? consultText(cur.next) : '예정 없음'],
                ['담당', cur.r.counselor_name ? cur.r.counselor_name + ' 상담원' : '—'],
              ].map(([k, v]) => (
                <div key={k} className="ma-row-k">
                  <span>{k}</span>
                  <span>{v}</span>
                </div>
              ))}
            </div>
            <div className="ma-acts">
              <Link className="ma-btn" to={`/AppBrief?case=${cur.r.id}`}>
                상담 전 브리핑
              </Link>
              <Link className="ma-btn ma-btn-p" to={`/AppRecord?case=${cur.r.id}`}>
                녹음 시작
              </Link>
              <Link className="ma-btn" to={`/AppUpload?case=${cur.r.id}`}>
                자료 올리기
              </Link>
              <Link className="ma-btn" to={`/AppMemo?case=${cur.r.id}`}>
                메모
              </Link>
            </div>
          </section>
        </div>
      )}
    </>
  );
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
