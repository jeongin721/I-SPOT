// 2 › 유형별 위험도 (AI 제안 · 심각도 1~5 · 상담원 판단)
// 원본: 다솔 님 디자인 counselor-web-design/RiskProfile.dc.html (front_new 브랜치). 화면 값은 아직 예시(가상) 데이터다.
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useCarryHref } from '../data/useCarryHref';
import { useTheme } from '../theme';
import './RiskProfile.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { lv: '', sev: {}, open: {} };
  }
  renderVals() {
    const s = this.state;
    const A = {
      physical: [
        '흔적 없는 가벼운 체벌, 단발',
        '경미한 흔적, 반복 체벌',
        '멍 · 통증이 남음, 도구 사용, 몸통 · 팔다리 상해',
        '머리 · 얼굴 · 목 상해, 반복적 도구 폭행, 병원 치료 필요',
        '골절 · 화상 · 목 조름 등 생명 위험',
      ],
      emotional: [
        '단발성 고성 · 꾸중, 반응 거의 없음',
        '반복적 고성 · 비하, 또는 함구 요구 1회',
        '위협 · 유기 위협 반복, 또는 두려움 · 위축 진술',
        '지속적 위협 · 고립, 가정폭력 반복 노출, 일상 기능 손상',
        '생명 위협, 극단적 공포, 자해 · 자살 언급',
      ],
      neglect: [
        '일시적 · 가벼운 돌봄 소홀',
        '식사 · 위생 소홀 반복, 건강 영향 없음',
        '지속적 방치, 결석 방치, 학령기 아동 장시간 방치',
        '건강 영향, 치료 방치, 영유아 방치',
        '유기, 생명 위협 수준의 방치',
      ],
      sexual: [
        '성적 수치심을 주는 언행, 단발',
        '반복적 성적 언행, 음란물 노출',
        '비접촉 성적 행위 요구 · 노출 · 촬영',
        '접촉을 동반한 성적 행위',
        '반복 · 지속적 접촉, 위협 · 강압 동반',
      ],
    };
    const T = [
      {
        k: 'physical',
        label: '신체학대',
        ev: '직접 근거',
        ai: 3,
        flag: 'S3',
        refs: ['8회차 00:41 피해아동 "…많이 때렸어요."', '8회차 01:08 피해아동 "등이랑 팔이요."'],
      },
      {
        k: 'emotional',
        label: '정서학대',
        ev: '직접 근거',
        ai: 3,
        flag: 'S5',
        refs: ['8회차 01:08 피해아동 "말하면 더 혼난다고 했어요."', '8회차 01:36 피해아동 "무서웠어요."'],
      },
      {
        k: 'neglect',
        label: '방임',
        ev: '확인 필요',
        ai: 0,
        flag: '',
        refs: ['8회차 02:15 화자 불확실 "밥도 안 줄 때가 있어요." · 신뢰도 0.70'],
      },
      {
        k: 'sexual',
        label: '성학대',
        ev: '언급 없음',
        ai: 0,
        flag: '',
        refs: ['언급 없음 ≠ 학대 없음 · 질문하지 않았을 수 있음'],
      },
    ];
    const evTone = {
      '직접 근거': ['#2B2A26', '#FFFFFF'],
      '확인 필요': ['#F2EFE8', '#66625A'],
      '언급 없음': ['#FFFFFF', '#98948B'],
    };
    const types = T.map((t) => {
      const cur = s.sev[t.k] !== undefined ? s.sev[t.k] : t.ai;
      const open = !!s.open[t.k];
      return {
        label: t.label,
        ev: t.ev,
        evBg: evTone[t.ev][0],
        evFg: evTone[t.ev][1],
        flag: !!t.flag,
        flagText: '안전 플래그 ' + t.flag,
        sevText: cur ? String(cur) : '–',
        sevSuffix: cur ? '/ 5' : t.ev === '확인 필요' ? '확인 후 판단' : '',
        fixed: s.sev[t.k] !== undefined && s.sev[t.k] !== t.ai,
        boxes: [1, 2, 3, 4, 5].map((n) => ({
          n,
          aria: t.label + ' 심각도 ' + n,
          bg: n <= cur ? (cur >= 4 ? '#A33B2E' : '#C2A36B') : '#FFFFFF',
          fg: n <= cur ? '#FFFFFF' : '#98948B',
          bd: n <= cur ? 'transparent' : '#DAD5C9',
          pick: () => this.setState({ sev: { ...s.sev, [t.k]: cur === n ? 0 : n } }),
        })),
        matched: cur
          ? cur + '단계 · ' + A[t.k][cur - 1]
          : t.ev === '확인 필요'
            ? '근거가 약해 단계를 매기지 않았어요'
            : '해당 내용 없음',
        refs: t.refs,
        open,
        toggleLabel: open ? '기준 닫기' : '기준 보기',
        toggle: () => this.setState({ open: { ...s.open, [t.k]: !open } }),
        anchors: A[t.k].map((text, i) => ({
          n: i + 1,
          text,
          bg: i + 1 === cur ? '#F1EADA' : 'transparent',
          fg: i + 1 === cur ? '#2B2A26' : '#7A776F',
          fw: i + 1 === cur ? 700 : 400,
        })),
      };
    });
    const levels = ['상', '중', '하'].map((l) => {
      const on = s.lv === l;
      const tone = l === '상' ? '#A33B2E' : l === '중' ? '#7A5F28' : '#66625A';
      return {
        label: l,
        on: on ? 'true' : 'false',
        bg: on ? (l === '상' ? '#F7E4DF' : l === '중' ? '#F3EAD3' : '#F2EFE8') : '#FFFFFF',
        bd: on ? tone : '#DAD5C9',
        fg: on ? tone : '#66625A',
        pick: () => this.setState({ lv: on ? '' : l }),
      };
    });
    return {
      types,
      levels,
      decisionNote: s.lv
        ? s.lv === '상'
          ? 'AI 제안과 같음 · 상담원 확정'
          : 'AI 제안(상)과 다름 · 상담원 판단으로 저장'
        : '아직 선택하지 않았어요',
      decisionShort: s.lv || '선택 전',
    };
  }
}

export default function RiskProfile(props) {
  // 사이드바의 내 정보 · 로그아웃 · '관리자 메뉴'(관리자일 때만)에만 쓴다. 이 화면의 값은 아직 예시 데이터다.
  const session = useAuthSession();
  const carry = useCarryHref();
  const theme = useTheme();
  const v = useDC(Logic, props);
  return (
    <div className="pg-RiskProfile">
      <div
        className={theme.cls}
        style={{
          minHeight: '1900px',
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
        <Sidebar active="CaseList" session={session} />
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
          <nav aria-label="위치" className="note">
            <A to="/CaseList">사례 관리</A> › <A to={carry('/CaseDetail')}>이서윤 C-2026-0351</A> ›{' '}
            <A to={carry('/CaseHistory')}>상담 이력</A> › <A to={carry('/SessionDetail')}>8회차</A>
          </nav>
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 280px' }}>
              <div className="sub">10/2(금) 방문상담</div>
              <h1 style={{ margin: '2px 0 0', fontSize: '28px', fontWeight: '700' }}>8회차 처리 · 이서윤</h1>
            </div>
          </header>
          <nav className="steps" aria-label="회차 처리 단계">
            <A className="stp done" to={carry('/SttReview')}>
              <span className="sn">✓</span>
              <b style={{ fontWeight: '500' }}>STT 검수</b>
            </A>
            <A className="stp on" to={carry('/SignalReview')} aria-current="step">
              <span className="sn">2</span>
              <b style={{ fontWeight: '700' }}>위험 신호 검토</b>
            </A>
            <A className="stp" to={carry('/NoteWrite')}>
              <span className="sn">3</span>
              <b style={{ fontWeight: '500' }}>요약 · 일지 작성</b>
            </A>
            <A className="stp" to={carry('/FollowupQ')}>
              <span className="sn">4</span>
              <b style={{ fontWeight: '500' }}>추가 확인 · 질문</b>
            </A>
          </nav>
          <nav className="seg" aria-label="2단계 보기" style={{ alignSelf: 'flex-start' }}>
            <A
              to={carry('/SignalReview')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                minHeight: '34px',
                padding: '0 13px',
                borderRadius: '9px',
                fontSize: '13px',
                color: '#66625A',
                textDecoration: 'none',
              }}
            >
              위험 신호
            </A>
            <button type="button" className="on">
              유형별 위험도
            </button>
          </nav>

          <section
            className="card"
            aria-label="위험도"
            style={{ padding: '22px 24px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '18px 28px' }}
          >
            <div style={{ flex: '1 1 280px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="note">AI 제안</span>
                <span className="chip c-ai">AI 초안</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px', marginTop: '4px' }}>
                <b style={{ fontSize: '30px', color: '#A33B2E' }}>상</b>
                <span style={{ fontSize: '14px' }}>안전 플래그 2개</span>
                <span className="note">· 7회차 중 → ↑ 증가</span>
              </div>
              <span className="sub2">S3 행위자 동거 + 직접 진술 · S5 함구 강요</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span className="note">상담원 판단</span>
              <div style={{ display: 'flex', gap: '6px' }} role="radiogroup" aria-label="상담원 위험도">
                {(v.levels || []).map((l, lIndex) => (
                  <Fragment key={lIndex}>
                    <button
                      type="button"
                      role="radio"
                      className="lvbtn"
                      aria-checked={l.on}
                      onClick={l.pick}
                      style={{ background: l.bg, borderColor: l.bd, color: l.fg }}
                    >
                      {l.label}
                    </button>
                  </Fragment>
                ))}
              </div>
              <span className="sub2">{v.decisionNote}</span>
            </div>
          </section>

          <section className="card" aria-label="유형별 심각도" style={{ overflow: 'hidden' }}>
            <div className="hd">
              <h2 className="h2">유형별 심각도</h2>
              <span className="note">높은 순 · 단계를 눌러 고칠 수 있어요</span>
            </div>
            {(v.types || []).map((t, tIndex) => (
              <Fragment key={tIndex}>
                <div className="trow">
                  <div>
                    <b style={{ fontSize: '16px' }}>{t.label}</b>
                    <span style={{ display: 'block', marginTop: '4px' }}>
                      <span className="chip" style={{ background: t.evBg, color: t.evFg }}>
                        {t.ev}
                      </span>
                    </span>
                    {t.flag ? (
                      <>
                        <span className="chip c-hi" style={{ marginTop: '6px' }}>
                          {t.flagText}
                        </span>
                      </>
                    ) : null}
                  </div>
                  <div>
                    <span className="note">심각도</span>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                      <b style={{ fontSize: '22px' }}>{t.sevText}</b>
                      <span className="note">{t.sevSuffix}</span>
                      {t.fixed ? (
                        <>
                          <span className="chip c-normal" style={{ height: '20px', fontSize: '11px' }}>
                            상담사 수정
                          </span>
                        </>
                      ) : null}
                    </div>
                    <div className="meter">
                      {(t.boxes || []).map((b, bIndex) => (
                        <Fragment key={bIndex}>
                          <button
                            type="button"
                            aria-label={b.aria}
                            onClick={b.pick}
                            style={{ background: b.bg, color: b.fg, borderColor: b.bd }}
                          >
                            {b.n}
                          </button>
                        </Fragment>
                      ))}
                    </div>
                  </div>
                  <div style={{ minWidth: '0' }}>
                    <span className="note">해당 기준</span>
                    <div style={{ fontSize: '14px', marginTop: '2px' }}>{t.matched}</div>
                    {(t.refs || []).map((r, rIndex) => (
                      <Fragment key={rIndex}>
                        <span className="sub2" style={{ display: 'block', marginTop: '4px' }}>
                          {r}
                        </span>
                      </Fragment>
                    ))}
                    {t.open ? (
                      <>
                        <div style={{ marginTop: '10px', padding: '8px', borderRadius: '10px', background: '#F7F6F2' }}>
                          {(t.anchors || []).map((a, aIndex) => (
                            <Fragment key={aIndex}>
                              <div className="anchor" style={{ background: a.bg, color: a.fg, fontWeight: a.fw }}>
                                <span>{a.n}</span>
                                <span>{a.text}</span>
                              </div>
                            </Fragment>
                          ))}
                        </div>
                      </>
                    ) : null}
                  </div>
                  <button type="button" className="btn btn-sm btn-s" onClick={t.toggle}>
                    {t.toggleLabel}
                  </button>
                </div>
              </Fragment>
            ))}
          </section>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '18px' }}>
            <section className="card" aria-label="회차별 추이" style={{ overflowX: 'auto' }}>
              <div className="hd">
                <h2 className="h2">회차별 추이</h2>
              </div>
              <table className="tbl mx">
                <thead>
                  <tr>
                    <th>유형</th>
                    <th>6회차</th>
                    <th>7회차</th>
                    <th>8회차</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>신체</td>
                    <td className="note">확인 필요</td>
                    <td>2</td>
                    <td>
                      <b>3</b>
                    </td>
                  </tr>
                  <tr>
                    <td>정서</td>
                    <td>2</td>
                    <td>2</td>
                    <td>
                      <b>3</b>
                    </td>
                  </tr>
                  <tr>
                    <td>방임</td>
                    <td className="note">–</td>
                    <td className="note">–</td>
                    <td className="note">확인 필요</td>
                  </tr>
                  <tr>
                    <td>성</td>
                    <td className="note">–</td>
                    <td className="note">–</td>
                    <td className="note">–</td>
                  </tr>
                  <tr>
                    <td>위험도 (상담원)</td>
                    <td>중</td>
                    <td>중</td>
                    <td>
                      <b>{v.decisionShort}</b>
                    </td>
                  </tr>
                </tbody>
              </table>
            </section>

            <section
              className="card"
              aria-label="안전 플래그와 재학대 요인"
              style={{ padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: '12px' }}
            >
              <h2 className="h2">안전 플래그 · 재학대 요인</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <div>
                  <span className="chip c-hi">S3</span> 행위자(친부) 동거 + 직접 진술
                  <span className="sub2" style={{ display: 'block' }}>
                    8회차 00:41 · 01:08
                  </span>
                </div>
                <div>
                  <span className="chip c-hi">S5</span> 함구 강요 "말하면 더 혼난다"
                  <span className="sub2" style={{ display: 'block' }}>
                    8회차 01:08
                  </span>
                </div>
                <div>
                  <span className="chip c-normal">S6 확인 후보</span> "할머니 집에 가고 싶어요" — 귀가 두려움인지 확인
                  <span className="sub2" style={{ display: 'block' }}>
                    8회차 02:40
                  </span>
                </div>
              </div>
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '6px',
                  paddingTop: '10px',
                  borderTop: '1px solid #EAE7DF',
                }}
              >
                <span className="note" style={{ width: '100%' }}>
                  위험요인 2 · 보호요인 1
                </span>
                <span className="chip c-normal">R1 중복 유형</span>
                <span className="chip c-normal">R7 친부가 행위자</span>
                <span className="chip c-sky" style={{ border: '1px solid #2B2A26', background: '#FFFFFF' }}>
                  P1 Key Person (조모)
                </span>
              </div>
            </section>
          </div>

          <section
            className="card"
            aria-label="확인할 것"
            style={{ padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: '8px' }}
          >
            <h2 className="h2">다음 상담에서 확인할 것</h2>
            <div>
              02:15 발화의 화자와 식사 상황 <span className="sub2">화자 불확실 · 신뢰도 0.70</span>
            </div>
            <div>
              등 · 팔 통증 이후 치료 여부 <span className="sub2">8회차 01:08</span>
            </div>
            <div>
              서로 다른 진술: 6회차 "맞은 적은… 잘 모르겠어요" ↔ 8회차 "많이 때렸어요"{' '}
              <span className="sub2">합치지 않고 그대로</span>
            </div>
          </section>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
            <A className="btn btn-s" to={carry('/SignalReview')}>
              ← 위험 신호
            </A>
            <A className="btn btn-p" to={carry('/NoteWrite')} style={{ marginLeft: 'auto' }}>
              확정 · 요약 · 일지 작성 →
            </A>
          </div>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
