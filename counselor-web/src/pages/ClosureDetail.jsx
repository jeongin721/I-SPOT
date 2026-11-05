// 종결 검토 › ② 사례관리 종결보고서 (서식 29 · AI 초안)
// 원본: 10/30 디자인 ClosureDetail.dc.html(프론트팀 zip). 화면 주소 ?case=<사례 ID>.
// 서버 연결(2026-10-30): 머리(사건번호 · 담당 · 아동 별칭 · 작성일 · 초기면접일), 초기상황 · 종결상황(저장한 글이 없으면 closure-summary
// AI 초안) · 종결 심의일 · 종결 상담일 · 종합의견 · '보고서 저장'(PUT closure-summary report). closureReview.ts closureReportValues.
// 실제 사례로 열면 예시 AI 제안 · 근거 · 기본값을 지운다.
// 11/03: 종결사유 · 안전평가 · Key Person · 안전점수도 report 에 저장한다(상담원이 고른 값만, AI 가 채우지 않음). 저장하면 카드 아래에
// '저장했습니다' 를 보이고, 저장하지 않은 수정이 있으면 떠날 때 묻는다(useLeaveGuard). 사례관리 제공 요약은 서버 칸이 없어 준비 중.
// 가족관계척도 줄은 기관 서식(가족관계 척도, useCaseForms) 가장 최근 기록의 평균을 보인다.
// 11/04 디자인: 'AI 제안' 자리를 실제 사례 값으로 — 안전평가 · Key Person 은 요약 AI 제안(summary.suggestions), 종결사유는 기록 제안,
// 종결 상담일은 일정, 학대유형은 AI 관련 신호, 사례관리 제공 요약은 회차 기록(report.services 로 저장). 칩 · 근거만 보이고
// 상담원 판단 칸은 채우지 않는다(closureSuggest.ts).
import { Fragment, useState } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import CopyButton from '../components/CopyButton';
import PrintNameDialog, { printMasked } from '../components/PrintNameDialog';
import Sidebar from '../components/Sidebar';
import NotiBell from '../components/NotiBell';
import ThemeToggle from '../components/ThemeToggle';
import { useSearchParams } from 'react-router-dom';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useCaseForms } from '../data/useCaseForms';
import { useCaseSchedule } from '../data/useCaseSchedule';
import { useSignalHistory } from '../data/useSignalHistory';
import { closureSuggestions } from '../data/screens/closureSuggest';
import { useClosureSummary } from '../data/useClosureSummary';
import { closureReportValues } from '../data/screens/closureReview';
import { familyScaleLine } from '../data/screens/caseForm';
import { signedIn } from '../data/screens/common';
import { readScreenIds } from '../data/screens/links';
import { useLeaveGuard } from '../data/screens/useLeaveGuard';
import { useTheme } from '../theme';
import './ClosureDetail.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { rs: {}, sa: {} };
  }
  renderVals() {
    const s = this.state;
    // 실제 사례(?case=)로 열면 예시 AI 제안 · 근거 · 기본값을 지운다(가상 사례 문장이 실제 사례 옆에 보이지 않게).
    const real = Boolean(this.props.connected);
    const sel = (on) => ({ bg: on ? '#FFFFFF' : 'transparent', fg: on ? '#2B2A26' : '#66625A', fw: on ? 700 : 400 });
    const R = [
      [
        '초기면접일 이후 지난 6개월간 재학대가 발생하지 않았을 경우',
        true,
        '3회차(5/8) 이후 새 학대 진술 · 재신고 없음 (10/10에 6개월 경과)',
      ],
      [
        '아동학대 재발 위험사유가 감소하였을 경우',
        true,
        '부모교육 8/8 이수 · 위험수준 척도 위험요인 14점 → 6점 (4월 → 10월)',
      ],
      ['「아동복지법」상 아동연령(18세) 초과', false, ''],
      [
        '피해아동의 안전이 보장되는 장기보호조치가 이루어진 경우 일정기간이 초과하였으나 가정복귀가 어렵다고 판단될 경우',
        false,
        '',
      ],
      ['피해아동이 사망하였을 경우', false, ''],
    ];
    const reasons = R.map(([t, aiRaw, evRaw], i) => {
      const ai = real ? false : aiRaw;
      const ev = real ? '' : evRaw;
      // 실제 사례는 서버에 저장한 값(r.reasons)을 쓴다.
      // 제안(기록 제안)은 칩 · 근거로만 보이고 체크하지 않는다.
      if (real) {
        const sg = this.props.suggest.reasons[i];
        return { t, on: Boolean(this.props.report.reasons[i]), hasEv: Boolean(sg), chip: sg?.chip ?? '', ev: sg?.ev ?? '', toggle: () => this.props.report.toggleReason(i) };
      }
      const on = s.rs[i] !== undefined ? s.rs[i] : ai;
      return { t, on, hasEv: !!ev, chip: 'AI 제안', ev, toggle: () => this.setState({ rs: { ...s.rs, [i]: !on } }) };
    });
    const goals = [
      ['장기 개입목표 1: 아동의 정서 안정', '아동 심리치료 12회 (○○센터) · 정서 표현 활동', 700, '12px'],
      ['단기 개입목표 1: 감정 표현하기', '상담 내 감정 카드 활동 6회', 400, '28px'],
      ['단기 개입목표 2: 안전 계획 익히기', '안전교육 4회 · 안전 계획 카드 제작', 400, '28px'],
      ['장기 개입목표 2: 보호자 양육 태도 개선', '부모교육 8회 이수 · 보호자 상담 6회', 700, '12px'],
      ['단기 개입목표 1: 비폭력 의사소통', '가족상담 3회', 400, '28px'],
      ['단기 개입목표 2: 양육 스트레스 관리', '가정방문 3회 · 양육 스트레스 상담 연계 1회', 400, '28px'],
    ].map(([k, v, fw, pad]) => ({ k, v, fw, pad }));
    const SA = [
      [
        '피해아동',
        [
          ['아동의 위험상황 인지 및 대처능력', '높음', '11회차 녹취 03:12 · 안전 계획을 자기 말로 설명함'],
          ['아동의 연령, 장애 등 집중적 보호가 요구되는 특성 보유', '보통', '초기면접지 · 만 7세, 장애 기록 없음'],
          ['피해아동과 가족과의 관계 친밀성', '높음', '체크인 기분 응답 4주 "좋아 · 보통" · 12회차 상담일지'],
        ],
      ],
      [
        '가족구성원',
        [
          ['가족구성원의 아동 안전 보호 및 양육 의지', '높음', '부모교육 8/8회 이수'],
          ['가정 내 가정폭력 문제', '낮음', '사례 기간 중 신고 · 진술 없음'],
          ['아동보호전문기관의 개입에 대한 태도', '높음', '가정방문 3회 모두 협조'],
          ['가족기능과 가정환경에 대한 평가', '', ''],
          ['주양육자의 양육역량', '보통', '부모교육 이수 · 9월 가정방문 기록'],
        ],
      ],
      [
        '사례관리대상자',
        [
          [
            '학대행위에 대한 잘못 인지 및 개선 의지',
            '높음',
            '보호자 상담 6회차 "소리 지른 게 아이한테 상처였다는 걸 알았어요"',
          ],
          ['스스로 자신을 통제하기 어려운 특성 (중독, 성격장애 등)', '', ''],
          ['가정 내 위기상황(실직, 가정폭력 등)으로 인한 만성적 스트레스', '보통', '보호자 상담 · 이직 준비 중'],
        ],
      ],
    ];
    let idx = 0;
    const safety = SA.map(([name, items]) => ({
      name,
      items: items.map(([q, aiRaw, evRaw]) => {
        const k = idx++;
        const sg = real ? this.props.suggest.safety[k] : null;
        const ai = real ? '' : aiRaw;
        const ev = real ? sg?.ev ?? '' : evRaw;
        const cur = real ? this.props.report.safety[k] : s.sa[k] !== undefined ? s.sa[k] : ai;
        return {
          q,
          ai,
          ev,
          chip: real ? sg?.chip ?? '' : `AI 제안 · ${ai}`,
          hasEv: real ? Boolean(sg) : !!ai,
          opts: ['높음', '보통', '낮음'].map((o) => ({
            label: o,
            ...sel(cur === o),
            pick: () => (real ? this.props.report.pickSafety(k, o) : this.setState({ sa: { ...s.sa, [k]: cur === o ? '' : o } })),
          })),
        };
      }),
    }));
    return { reasons, goals: real ? [] : goals, safety, scoreRows: ['피해아동 응답', '가족구성원 응답', '사례관리대상자 응답'] };
  }
}

// 사례가 바뀌면(같은 화면에서 다른 사례 주소로 · 뒤로 가기) 화면을 새로 만든다. 고친 칸(draft)이 사례 구분 없이 남아 있으면
// 앞 사례에서 저장하지 않은 입력이 다음 사례 보고서에 저장된다(Codex #140 H1, 11/03).
export default function ClosureDetail(props) {
  const { caseId } = readScreenIds(useSearchParams()[0]);
  return <ClosureDetailScreen key={caseId ?? ''} {...props} />;
}

function ClosureDetailScreen(props) {
  const [outOpen, setOutOpen] = useState(false);
  const session = useAuthSession();
  const theme = useTheme();
  const { caseId } = readScreenIds(useSearchParams()[0]);
  const enabled = signedIn(session);
  const detail = useCaseDetail(caseId, { enabled });
  const summary = useClosureSummary(caseId, { enabled });
  const [draft, setDraftState] = useState({});
  const live = enabled && Boolean(caseId && detail.caseInfo);
  const forms = useCaseForms(caseId, { enabled: live });
  const history = useSignalHistory(caseId, { enabled: live });
  const plan = useCaseSchedule(caseId, { enabled: live });
  const suggest = closureSuggestions({
    detail,
    history: history.sessions,
    forms: forms.items,
    events: plan.events,
    summary: summary.record?.summary ?? null,
    today: new Date().toISOString().slice(0, 10),
  });
  const r = closureReportValues(
    caseId,
    detail,
    summary,
    draft,
    (patch) => setDraftState((current) => ({ ...current, ...patch })),
    () => setDraftState({}),
    suggest.services,
  );
  const v = useDC(Logic, { ...props, connected: r.connected, report: r, suggest });
  const family = familyScaleLine(forms);
  const [savedNote, setSavedNote] = useState('');
  useLeaveGuard(r.unsaved, { guardBack: true });
  const save = async () => {
    setSavedNote('');
    if (await r.save()) {
      const now = new Date();
      setSavedNote(`보고서를 저장했습니다 · ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`);
    }
  };
  const name = r.alias || '강시우';
  return (
    <div className="pg-ClosureDetail">
      <div
        className={theme.cls}
        style={{
          minHeight: '2250px',
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
        <Sidebar active="Closure" session={session} />
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
            <NotiBell session={session} />
            <ThemeToggle />
          </div>
          <nav aria-label="위치" className="note">
            <A to="/Closure">종결 검토</A> › {r.crumb}
          </nav>
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px 16px' }}>
            <A className="btn btn-sm btn-s" to={r.reviewHref}>
              ← 전체 상담 내역 검토
            </A>
            <div style={{ flex: '1 1 320px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>사례관리 종결보고서</h1>
                {!r.connected || summary.record?.summary?.source === 'AI' ? <span className="chip c-ai">AI 초안</span> : null}
              </div>
              <div className="note">서식 29</div>
            </div>
            <A className="btn btn-s" to={r.caseHref}>
              사례 상세 보기
            </A>
          </header>
          <nav className="steps" aria-label="종결 검토 단계">
            <A className="stp done" to={r.reviewHref}>
              <span className="sn">✓</span>
              <b style={{ fontWeight: '500' }}>전체 상담 내역 검토</b>
            </A>
            <A className="stp on" to={r.detailHref} aria-current="step">
              <span className="sn">2</span>
              <b style={{ fontWeight: '700' }}>종결보고서 작성</b>
            </A>
          </nav>

          <section
            className="card"
            style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '16px' }}
          >
            <div className="fhead">
              <div>
                <span className="k">사건번호</span>
                <span className="v">{r.head ? r.head.caseNumber : '—'}</span>
              </div>
              <div>
                <span className="k">학대유형</span>
                <span className="v">
                  {r.connected && suggest.abuseSignal ? (
                    <>
                      <span className="chip c-ai no-print" style={{ height: '20px', fontSize: '11px' }}>
                        {suggest.abuseSignal}
                      </span>
                      <span className="print-only">—</span>
                    </>
                  ) : (
                    '—'
                  )}
                </span>
              </div>
              <div>
                <span className="k">담당 상담원</span>
                <span className="v">{r.head ? r.head.counselor : '—'}</span>
              </div>
              <div>
                <span className="k">아동 별칭</span>
                <span className="v">{r.head ? r.head.child : '—'}</span>
              </div>
              <div>
                <span className="k">작성일</span>
                <span className="v">{r.head ? r.head.today : '—'}</span>
              </div>
              <div>
                <span className="k">초기면접일</span>
                <span className="v">{r.head ? r.head.firstInterview : '—'}</span>
              </div>
            </div>

            <div className="grp">종결사유</div>
            {(v.reasons || []).map((r, rIndex) => (
              <Fragment key={rIndex}>
                <label className="ck">
                  <input type="checkbox" checked={r.on} onChange={r.toggle} />
                  <span style={{ flex: '1' }}>
                    {r.t}
                    {r.hasEv ? (
                      <>
                        <span className="ev" style={{ marginTop: '4px' }}>
                          <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                            {r.chip}
                          </span>
                          {r.ev}
                        </span>
                      </>
                    ) : null}
                  </span>
                </label>
              </Fragment>
            ))}

            <div className="grp">사례관리 제공 요약</div>
            <div style={{ border: '1px solid #E7E4DC', borderRadius: '12px', overflow: 'hidden' }}>
              <div className="goal" style={{ background: '#F2EFE8', fontSize: '13px', color: '#66625A' }}>
                <span>개입목표</span>
                <span>
                  제공된 서비스 내용 및 총량{' '}
                  {!r.connected || suggest.servicesChip ? (
                    <span className="chip c-ai" style={{ height: '20px', fontSize: '11px', marginLeft: '6px' }}>
                      {r.connected ? suggest.servicesChip : 'AI 초안 · 서비스 기록'}
                    </span>
                  ) : null}
                </span>
              </div>
              {r.connected ? (
                <div className="goal">
                  <span className="k" style={{ fontWeight: 700, paddingLeft: '12px' }}>
                    상담 · 서비스 제공 <span className="note" style={{ fontWeight: 400 }}>(개입목표 준비 중)</span>
                  </span>
                  <input
                    className="inp"
                    type="text"
                    value={r.services.value}
                    onChange={r.services.onChange}
                    maxLength={300}
                    aria-label="제공된 서비스 내용 및 총량"
                    style={{ width: '100%', height: '36px' }}
                  />
                </div>
              ) : null}
              {(v.goals || []).map((g, gIndex) => (
                <Fragment key={gIndex}>
                  <div className="goal">
                    <span className="k" style={{ fontWeight: g.fw, paddingLeft: g.pad }}>
                      {g.k}
                    </span>
                    <input
                      className="inp"
                      type="text"
                      defaultValue={g.v}
                      aria-label={g.k}
                      style={{ width: '100%', height: '36px' }}
                    />
                  </div>
                </Fragment>
              ))}
            </div>

            <div className="grp">안전평가</div>
            {(v.safety || []).map((g, gIndex) => (
              <Fragment key={gIndex}>
                <b style={{ fontSize: '13px', color: '#66625A', padding: '4px 4px 0' }}>{g.name}</b>
                {(g.items || []).map((it, itIndex) => (
                  <Fragment key={itIndex}>
                    <div className="item">
                      <span>{it.q}</span>
                      <span className="opt3" role="group" aria-label={it.q}>
                        {(it.opts || []).map((o, oIndex) => (
                          <Fragment key={oIndex}>
                            <button
                              type="button"
                              onClick={o.pick}
                              style={{ background: o.bg, color: o.fg, fontWeight: o.fw }}
                            >
                              {o.label}
                            </button>
                          </Fragment>
                        ))}
                      </span>
                      {it.hasEv ? (
                        <>
                          <span className="ev">
                            <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                              {it.chip}
                            </span>
                            {it.ev}
                          </span>
                        </>
                      ) : null}
                    </div>
                  </Fragment>
                ))}
              </Fragment>
            ))}
            <b style={{ fontSize: '13px', color: '#66625A', padding: '4px 4px 0' }}>환경</b>
            <div className="item" style={{ gridTemplateColumns: 'minmax(0, 1.2fr) minmax(0, 1fr)' }}>
              <span>조부모, 친구, 이웃 등 신뢰할만한 주위 사람 (Key Person)</span>
              {/* 연결 상태가 바뀌면 다시 그려 처음(연결 전)에 들어간 예시 글이 실제 사례에 남지 않게(민규 #128 교차검증). */}
              <input
                key={r.connected ? 'live' : 'sample'}
                className="inp"
                type="text"
                {...(r.connected
                  ? { value: r.keyPerson.value, onChange: r.keyPerson.onChange, maxLength: 300 }
                  : { defaultValue: '있음 · 외조모 (주 2회 돌봄)' })}
                aria-label="Key Person"
                style={{ width: '100%' }}
              />
              {!r.connected || suggest.keyPerson ? (
                <span className="ev">
                  <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                    AI 제안
                  </span>
                  {r.connected ? suggest.keyPerson.ev : '보호자 상담 3회차 · 서비스 기록'}
                </span>
              ) : null}
            </div>

            <div className="grp">
              안전점수{' '}
              <span className="note" style={{ fontWeight: '400' }}>
                (최소안전 1점 – 가장안전 10점)
              </span>
            </div>
            {(v.scoreRows || []).map((row, rIndex) => (
              <Fragment key={rIndex}>
                <div className="item" style={{ gridTemplateColumns: '160px 110px minmax(0, 1fr)' }}>
                  <span>{row}</span>
                  <input
                    className="inp"
                    type="number"
                    min="1"
                    max="10"
                    placeholder="( )점"
                    aria-label="안전점수"
                    style={{ width: '100px' }}
                    {...(r.connected
                      ? { value: r.scores[rIndex].score, onChange: (e) => r.scores[rIndex].setScore(e.target.value) }
                      : {})}
                  />
                  <input
                    className="inp"
                    type="text"
                    placeholder="이유"
                    aria-label="이유"
                    style={{ width: '100%' }}
                    {...(r.connected
                      ? {
                          value: r.scores[rIndex].reason,
                          onChange: (e) => r.scores[rIndex].setReason(e.target.value),
                          maxLength: 300,
                        }
                      : {})}
                  />
                </div>
              </Fragment>
            ))}
            <div className="item" style={{ gridTemplateColumns: '160px minmax(0, 1fr)' }}>
              <span>가족관계척도</span>
              {r.connected ? (
                family.avg ? (
                  <span>
                    평균 <b className="brn">{family.avg}</b>점 <span className="note">· {family.sub}</span>
                  </span>
                ) : (
                  <span className="note">{family.sub}</span>
                )
              ) : (
                <span>
                  평균 <b className="brn">3.60</b>점{' '}
                  <span className="note">· 10/1 응답 (모) · 초기 4/12 응답 2.40점</span>
                </span>
              )}
            </div>

            <div className="grp">대상자 변화상황</div>
            <div className="two">
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <span style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <b style={{ fontSize: '14px' }}>초기상황</b>
                  {r.initialChip ? (
                    <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                      {r.initialChip}
                    </span>
                  ) : null}
                </span>
                <textarea className="ta2" style={{ minHeight: '120px' }} value={r.initial.value} onChange={r.initial.onChange}></textarea>
                <CopyButton name={name} />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <span style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <b style={{ fontSize: '14px' }}>종결상황</b>
                  {r.closingChip ? (
                    <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                      {r.closingChip}
                    </span>
                  ) : null}
                </span>
                <textarea className="ta2" style={{ minHeight: '120px' }} value={r.closing.value} onChange={r.closing.onChange}></textarea>
                <CopyButton name={name} />
              </label>
            </div>

            <div className="two">
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <b style={{ fontSize: '14px' }}>종결 심의일</b>
                <input className="inp" type="date" aria-label="종결 심의일" value={r.reviewDate.value} onChange={r.reviewDate.onChange} />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <b style={{ fontSize: '14px' }}>종결 상담일</b>
                <input className="inp" type="date" aria-label="종결 상담일" value={r.closingDate.value} onChange={r.closingDate.onChange} />
                {!r.connected || suggest.closingDate ? (
                  <span className="ev">
                    <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                      {r.connected ? suggest.closingDate.chip : 'AI 제안'}
                    </span>
                    {r.connected ? suggest.closingDate.ev : '일정 · 10/14 종결 상담'}
                  </span>
                ) : null}
              </label>
            </div>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <b style={{ fontSize: '14px' }}>담당 상담원 종합의견</b>
              <textarea className="ta2" style={{ minHeight: '110px' }} placeholder="상담원 작성" value={r.opinion.value} onChange={r.opinion.onChange}></textarea>
              <CopyButton name={name} />
            </label>

            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                justifyContent: 'flex-end',
                gap: '10px',
              }}
            >
              <button type="button" className="btn btn-s" aria-haspopup="dialog" onClick={() => setOutOpen(true)}>
                PDF · HWP로 내보내기
              </button>
              {outOpen ? (
                <PrintNameDialog
                  title="PDF · HWP로 내보내기"
                  goLabel="내보내기"
                  name={name}
                  onClose={() => setOutOpen(false)}
                  onRun={(mask) => {
                    setOutOpen(false);
                    printMasked({ name, mask });
                  }}
                />
              ) : null}
              {/* 일정 달력이 '사례회의 · 종결평가 회의' 추가 창을 연 채로 열린다 — 날을 고르고 저장하면 일정이 잡힌다(11/02). */}
              <A className="btn btn-s" to={r.meetingHref}>
                종결평가 회의 일정 잡기
              </A>
              <button type="button" className="btn btn-p" onClick={save} disabled={!r.canSave}>
                {r.saveLabel}
              </button>
            </div>
          </section>
          {savedNote || r.reportNote ? (
            <p className="note" role="status" style={{ margin: 0 }}>
              {savedNote || r.reportNote}
            </p>
          ) : null}
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
