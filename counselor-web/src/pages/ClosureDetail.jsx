// 종결 검토 › ② 사례관리 종결보고서 (서식 29 · AI 초안)
// 원본: 다솔 님 디자인 counselor-web-design/ClosureDetail.dc.html (front_new 브랜치). 화면 값은 아직 예시(가상) 데이터다.
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useTheme } from '../theme';
import './ClosureDetail.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { rs: {}, sa: {} };
  }
  renderVals() {
    const s = this.state;
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
    const reasons = R.map(([t, ai, ev], i) => {
      const on = s.rs[i] !== undefined ? s.rs[i] : ai;
      return { t, on, hasEv: !!ev, ev, toggle: () => this.setState({ rs: { ...s.rs, [i]: !on } }) };
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
      items: items.map(([q, ai, ev]) => {
        const k = idx++;
        const cur = s.sa[k] !== undefined ? s.sa[k] : ai;
        return {
          q,
          ai,
          ev,
          hasEv: !!ai,
          opts: ['높음', '보통', '낮음'].map((o) => ({
            label: o,
            ...sel(cur === o),
            pick: () => this.setState({ sa: { ...s.sa, [k]: cur === o ? '' : o } }),
          })),
        };
      }),
    }));
    return { reasons, goals, safety, scoreRows: ['피해아동 응답', '가족구성원 응답', '사례관리대상자 응답'] };
  }
}

export default function ClosureDetail(props) {
  // 사이드바의 내 정보 · 로그아웃 · '관리자 메뉴'(관리자일 때만)에만 쓴다. 이 화면의 값은 아직 예시 데이터다.
  const session = useAuthSession();
  const theme = useTheme();
  const v = useDC(Logic, props);
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
            <ThemeToggle />
          </div>
          <nav aria-label="위치" className="note">
            <A to="/Closure">종결 검토</A> › 강시우
          </nav>
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px 16px' }}>
            <A className="btn btn-sm btn-s" to="/ClosureReview">
              ← 전체 상담 내역 검토
            </A>
            <div style={{ flex: '1 1 320px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>사례관리 종결보고서</h1>
                <span className="chip c-ai">AI 초안</span>
              </div>
              <div className="note">서식 29</div>
            </div>
            <A className="btn btn-s" to="/CaseDetail">
              사례 상세 보기
            </A>
          </header>
          <nav className="steps" aria-label="종결 검토 단계">
            <A className="stp done" to="/ClosureReview">
              <span className="sn">✓</span>
              <b style={{ fontWeight: '500' }}>전체 상담 내역 검토</b>
            </A>
            <A className="stp on" to="/ClosureDetail" aria-current="step">
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
                <span className="v">C-2026-0312</span>
              </div>
              <div>
                <span className="k">학대유형</span>
                <span className="v">정서</span>
              </div>
              <div>
                <span className="k">담당 상담원</span>
                <span className="v">이서연</span>
              </div>
              <div>
                <span className="k">아동성명</span>
                <span className="v">강시우 (만 7세)</span>
              </div>
              <div>
                <span className="k">작성일</span>
                <span className="v">2026-10-12</span>
              </div>
              <div>
                <span className="k">초기면접일</span>
                <span className="v">2026-04-10</span>
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
                            AI 제안
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
                  <span className="chip c-ai" style={{ height: '20px', fontSize: '11px', marginLeft: '6px' }}>
                    AI 초안 · 서비스 기록
                  </span>
                </span>
              </div>
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
                              AI 제안 · {it.ai}
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
              <input
                className="inp"
                type="text"
                defaultValue="있음 · 외조모 (주 2회 돌봄)"
                aria-label="Key Person"
                style={{ width: '100%' }}
              />
              <span className="ev">
                <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                  AI 제안
                </span>
                보호자 상담 3회차 · 서비스 기록
              </span>
            </div>

            <div className="grp">
              안전점수{' '}
              <span className="note" style={{ fontWeight: '400' }}>
                (최소안전 1점 – 가장안전 10점)
              </span>
            </div>
            {(v.scoreRows || []).map((r, rIndex) => (
              <Fragment key={rIndex}>
                <div className="item" style={{ gridTemplateColumns: '160px 110px minmax(0, 1fr)' }}>
                  <span>{r}</span>
                  <input
                    className="inp"
                    type="number"
                    min="1"
                    max="10"
                    placeholder="( )점"
                    aria-label="안전점수"
                    style={{ width: '100px' }}
                  />
                  <input className="inp" type="text" placeholder="이유" aria-label="이유" style={{ width: '100%' }} />
                </div>
              </Fragment>
            ))}
            <div className="item" style={{ gridTemplateColumns: '160px minmax(0, 1fr)' }}>
              <span>가족관계척도</span>
              <span>
                평균 <b className="brn">3.60</b>점{' '}
                <span className="note">· 10/1 응답 (모) · 초기 4/12 응답 2.40점</span>
              </span>
            </div>

            <div className="grp">대상자 변화상황</div>
            <div className="two">
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <span style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <b style={{ fontSize: '14px' }}>초기상황</b>
                  <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                    AI 초안 · 초기면접지 4/10
                  </span>
                </span>
                <textarea
                  className="ta2"
                  style={{ minHeight: '120px' }}
                  defaultValue={
                    '보호자(모)의 잦은 고성 · 위협적 언어로 아동이 위축됨. 아동은 "엄마가 소리 지르면 숨고 싶어요"라고 진술함. 보호자는 훈육이라고 인식함.'
                  }
                ></textarea>
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <span style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <b style={{ fontSize: '14px' }}>종결상황</b>
                  <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                    AI 초안 · 9~12회차
                  </span>
                </span>
                <textarea
                  className="ta2"
                  style={{ minHeight: '120px' }}
                  defaultValue={
                    '9~12회차 상담과 체크인에서 새 학대 진술 없음. 아동이 안전 계획을 스스로 설명함. 보호자는 부모교육 8회를 이수하고 고성이 상처였다고 말함.'
                  }
                ></textarea>
              </label>
            </div>

            <div className="two">
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <b style={{ fontSize: '14px' }}>종결 심의일</b>
                <input className="inp" type="date" aria-label="종결 심의일" />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <b style={{ fontSize: '14px' }}>종결 상담일</b>
                <input className="inp" type="date" defaultValue="2026-10-14" aria-label="종결 상담일" />
                <span className="ev">
                  <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                    AI 제안
                  </span>
                  일정 · 10/14 종결 상담
                </span>
              </label>
            </div>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <b style={{ fontSize: '14px' }}>담당 상담원 종합의견</b>
              <textarea className="ta2" style={{ minHeight: '110px' }} placeholder="상담원 작성"></textarea>
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
              <button type="button" className="btn btn-s">
                PDF · HWP로 내보내기
              </button>
              <A className="btn btn-s" to="/Schedule">
                종결평가 회의 일정 잡기
              </A>
              <button type="button" className="btn btn-p">
                보고서 저장
              </button>
            </div>
          </section>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
