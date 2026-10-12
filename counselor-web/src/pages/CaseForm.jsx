// 탭 5 › 기관 서식 작성 (사정기록지 안전영역 · 사례관리 점검표 · 위험수준 척도 · 가족관계 척도)
// 원본: I-SPOT 디자인 캔버스 보드 CaseForm.dc.html (자동 변환 후 다듬어 쓰세요)
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import './CaseForm.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { tab: 'A', sa: {}, key: '있음', res: '', ck: {}, sc: {}, who: '부', fam: {} };
  }
  renderVals() {
    const s = this.state;
    const sel = (on) => ({
      bg: on ? '#E2ECF8' : 'transparent',
      fg: on ? '#2E5687' : '#55606A',
      fw: on ? 700 : 400,
      bd: on ? 'inset 0 0 0 1px #A8C6E7' : 'none',
    });
    const tabs = [
      ['A', '사정기록지 · 안전영역'],
      ['B', '사례관리 점검표'],
      ['C', '위험수준별 개입 사정 척도'],
      ['D', '가족관계 척도'],
    ].map(([k, label]) => ({
      label,
      cls: s.tab === k ? 'on' : '',
      on: s.tab === k ? 'true' : 'false',
      pick: () => this.setState({ tab: k }),
    }));
    // 안전영역 (서식 6 · 서식 29 공통 문항)
    const SA = [
      [
        '피해아동',
        [
          ['아동의 위험상황 인지 및 대처능력', '보통', '7회차(9/18) 안전 계획을 자기 말로 설명함'],
          [
            '아동의 연령, 장애 등 집중적 보호가 요구되는 특성 보유',
            '낮음',
            '초기면접지 · 만 13세, 장애 기록 없음',
          ],
          [
            '피해아동과 가족과의 관계 친밀성',
            '보통',
            '6회차 "아빠가 소리 지르는 게 제일 싫어요" · 조모와 관계 긍정',
          ],
        ],
      ],
      [
        '가족구성원',
        [
          ['가족구성원의 아동 안전 보호 및 양육 의지', '보통', '부모교육 3/8회 출석 · 2회 연속 결석'],
          ['가정 내 가정폭력 문제', '', ''],
          ['아동보호전문기관의 개입에 대한 태도', '낮음', '보호자 상담 일정 2회 연기 (9/18, 10/2)'],
          ['가족기능과 가정환경에 대한 평가', '', ''],
          ['주양육자의 양육역량', '보통', '부모교육 출석 기록 · 7회차 상담일지'],
        ],
      ],
      [
        '사례관리대상자',
        [
          [
            '학대행위에 대한 잘못 인지 및 개선 의지',
            '낮음',
            '7회차 05:10 "아빠가 그 얘기 하지 말랬어요" (함구 요구)',
          ],
          ['스스로 자신을 통제하기 어려운 특성 (중독, 성격장애 등)', '', ''],
          ['가정 내 위기상황(실직, 가정폭력 등)으로 인한 만성적 스트레스', '', ''],
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
    const keyOpts = ['있음', '없음'].map((o) => ({
      label: o,
      ...sel(s.key === o),
      pick: () => this.setState({ key: o }),
    }));
    const scoreRows = ['피해아동 응답', '가족구성원 응답', '사례관리대상자 응답'].map((who) => ({ who }));
    const resultOpts = ['집중관리 사례', '일반관리 사례', '모니터링관리 사례'].map((o) => ({
      label: o,
      ...sel(s.res === o),
      pick: () => this.setState({ res: s.res === o ? '' : o }),
    }));
    // 서식 27 점검표
    const CK = [
      [
        '사례관리 계획에 따라 서비스가 적절하게 제공되고 있는가?',
        '아니오',
        '부모교육 2회 연속 결석 (9/18, 10/2)',
      ],
      [
        '학대피해아동과 비공식적인 지지망 그리고 전문적 보호체계의 노력이 적절한가?',
        '예',
        '조모 연락 체계 · 아동 심리치료 6/12회',
      ],
      [
        '학대피해아동 가정이 안전하며 학대 위험이 감소하고 있는가? (소견에 구체적 근거 작성)',
        '아니오',
        '8회차(10/2) 신체 학대 진술 · 체크인 QB-E-05 "없어 → 1번"',
      ],
      ['제공되는 서비스에 대해 학대피해아동과 가족이 만족하고 있는가?', '', ''],
      [
        '다른 서비스 욕구가 발생하였는가?',
        '예',
        '등 · 팔 통증 치료 여부 미확인 (8회차 01:08) → 의료 지원 검토',
      ],
      ['사례관리 지속이 필요한가?', '예', '위 3번 근거'],
      ['재사정이 필요한가?', '예', '새 진술로 위험요인 변화'],
      ['사례관리 계획은 수정되어야 하는가?', '예', '부모교육 일정 · 의료 연계 반영 필요'],
      ['사례는 종결되어야 하는가?', '아니오', '위 3번 근거'],
    ];
    const checks = CK.map(([q, ai, ev], i) => {
      const cur = s.ck[i] !== undefined ? s.ck[i] : ai;
      return {
        q: `${i + 1}. ${q}`,
        ai,
        ev,
        hasEv: !!ai,
        opts: ['예', '아니오'].map((o) => ({
          label: o,
          ...sel(cur === o),
          pick: () => this.setState({ ck: { ...s.ck, [i]: cur === o ? '' : o } }),
        })),
      };
    });
    // 참고자료 3 · 43문항
    const Q = [
      '아동은 질환을 가지고 있다.',
      '아동은 인터넷(핸드폰) 과의존 상태이다.',
      '아동은 신체 및 정신장애를 가지고 있다.',
      '아동이 신체적 상흔이나 손상을 가지고 있다.',
      '아동은 또래에 비해 발달상태가 느리다.',
      '아동은 자해행위 또는 자살을 시도한 적이 있다.',
      '아동은 심리적인 어려움을 가지고 있다.',
      '아동은 다른 사람과의 관계에 어려움이 있다.',
      '아동은 의사소통이 어렵다.',
      '아동이 비행행동을 하였다.',
      '아동이 성과 관련된 문제행동을 보인다.',
      '아동이 청결하지 못한 상태이다.',
      '아동이 아동보호전문기관 등의 개입에 거부적이다.',
      '아동이 사회로부터 고립되어 있다.',
      '주거환경이 열악하거나 불안정하다.',
      '지역사회 내에 모니터링 체계가 없다.',
      '동거가족 중 112 등에 신고된 사람이 있다.',
      '가족이 스트레스 상황에 노출되어 있다.',
      '주양육자는 사례관리대상자의 치료나 변화에 개입할 의지가 없다.',
      '주양육자가 사례관리대상자를 옹호하려고 한다.',
      '주양육자는 사례관리대상자에 대한 의존도가 높다.',
      '주양육자는 아동 양육을 위한 적절한 지식을 가지고 있다.',
      '주양육자는 보호자로서 자신의 역할을 이해하고 있다.',
      '주양육자는 학대에 대해 민감하다.',
      '주양육자는 자신의 욕구보다 아동의 욕구를 우선한다.',
      '주양육자는 아동의 기본적인 욕구를 충족시킨다.',
      '주양육자는 상황에 맞게 감정을 조절할 수 있다.',
      '주양육자는 장애가 없다.',
      '주양육자는 질환이 없다.',
      '주양육자는 양육에 있어서 적극적이다.',
      '주양육자는 아이의 정서에 따라 반응할 수 있다.',
      '주양육자는 아동에게 너그럽다.',
      '주양육자와 아동은 정서적 유대를 가지고 상호 간에 애착을 형성하고 있다.',
      '주양육자는 아동에 대해 현실적인 기대를 가지고 있다.',
      '주양육자는 긍정적인 생각과 태도를 가지고 있다.',
      '주양육자를 지지해주는 가족이 있다.',
      '가족에게 비공식적인 사회적 지지체계가 있다.',
      '가족에게 공식적인 사회적 지지체계가 있다.',
      '주양육자는 주변에 도움을 적극적으로 요청한다.',
      '주양육자는 아동보호전문기관 등의 개입에 수용적이다.',
      '주양육자는 사례관리대상자로부터 아동을 보호할 수 있다.',
      '아동은 자기보호능력이 있어서 학대로부터 스스로를 보호할 수 있다.',
      '주양육자 외 가족 내 양육을 도와주는 사람이 있다.',
    ];
    const AIV = {
      4: [2, '8회차 01:08 "등이랑 팔이요" (상흔 확인은 상담원 관찰)'],
      7: [2, '체크인 기분 "조금 걱정돼" 2주 · 심리치료 중'],
      13: [0, '상담 출석 8/8회'],
      18: [2, '8회차 상담일지 · 가정 내 긴장'],
      20: [2, '7회차 "아빠가 그 얘기 하지 말랬어요"'],
      26: [1, '8회차 02:15 식사 관련 발화 (화자 확인 중)'],
      36: [2, '조모 지지 (7회차 안전 계획)'],
      37: [2, '조모 · 학교 담임 연락 체계'],
      38: [2, '심리치료 연계 (○○센터)'],
      40: [1, '보호자 상담 일정 2회 연기'],
      42: [1, '7회차 안전 계획을 스스로 설명함'],
      43: [2, '조모가 주 2회 돌봄'],
    };
    let rs = 0,
      ps = 0,
      filled = 0;
    const scale = Q.map((q, i) => {
      const n = i + 1;
      const ai = AIV[n];
      const v = s.sc[n] !== undefined ? s.sc[n] : ai ? ai[0] : null;
      if (v !== null && v !== '') {
        filled++;
        if (n <= 21) rs += v;
        else ps += v;
      }
      return {
        n,
        q,
        head: n === 1 || n === 22,
        headLabel: n === 1 ? '위험요인 (1~21)' : '보호요인 (22~43)',
        ev: ai ? `AI 제안 ${ai[0]}점 · ${ai[1]}` : '',
        opts: [0, 1, 2, 3].map((o) => ({
          label: o + '점',
          ...sel(v === o),
          pick: () => this.setState({ sc: { ...s.sc, [n]: v === o ? '' : o } }),
        })),
      };
    });
    // 참고자료 1 · 15문항
    const F = [
      '우리 가족은 가족끼리 대화가 잘 된다',
      '우리 가족은 문제를 함께 잘 해결하려고 노력한다',
      '우리 가족은 서로에 대해 잘 알고 있다',
      '우리 가족은 각자의 장점에 대해 가족들에게 마음을 열고 허심탄회하게 이야기한다',
      '우리 가족은 도움이 필요할 때 언제든지 서로 도움을 청할 수 있다',
      '우리 가족은 여가시간을 함께 보내기를 좋아한다',
      '우리 가족은 서로 친밀하게 느낀다',
      '우리 가족은 솔직하고 정직하다',
      '우리 가족은 서로 지지해주고 격려해준다',
      '우리 가족은 서로에게 생각과 느낌을 표현할 수 있다',
      '가족의 일을 계획할 때 우리 가족 모두에게 발언권이 있다',
      '우리 가족은 서로를 있는 그대로 인정한다',
      '우리 가족은 각각 자신의 행동에 책임을 진다',
      '우리 가족은 가족들 간의 서로 다른 의견을 존중한다',
      '우리 가족은 서로의 강점을 존중한다',
    ];
    let fs = 0,
      fn = 0;
    const fam = F.map((q, i) => {
      const v = s.fam[i];
      if (v) {
        fs += v;
        fn++;
      }
      return {
        n: i + 1,
        q,
        opts: [1, 2, 3, 4, 5].map((o) => ({
          label: String(o),
          ...sel(v === o),
          pick: () => this.setState({ fam: { ...s.fam, [i]: v === o ? 0 : o } }),
        })),
      };
    });
    const resp = ['부', '모', '아동'].map((o) => ({
      label: o,
      ...sel(s.who === o),
      pick: () => this.setState({ who: o }),
    }));
    return {
      tabs,
      tA: s.tab === 'A',
      tB: s.tab === 'B',
      tC: s.tab === 'C',
      tD: s.tab === 'D',
      goC: () => this.setState({ tab: 'C' }),
      safety,
      keyOpts,
      scoreRows,
      resultOpts,
      checks,
      scale,
      riskSum: rs,
      protSum: ps,
      filled,
      fam,
      resp,
      famAvg: fn ? (fs / 15).toFixed(2) : '—',
      famN: fn,
    };
  }
}

export default function CaseForm(props) {
  const v = useDC(Logic, props);
  return (
    <div className="pg-CaseForm">
      <div
        style={{
          minHeight: '1880px',
          background: '#FFFEFA',
          color: '#2F3A44',
          fontFamily: "'Noto Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'stretch',
        }}
      >
        <aside className="side" aria-label="주 메뉴">
          <A className="logo" to="/Main">
            <span className="mk">IS</span>
            <b style={{ fontSize: '17px' }}>I-SPOT</b>
          </A>
          <A className="cta" to="/UploadModal">
            ↑ 녹취 · 자료 올리기
          </A>
          <A className="cta2" to="/CaseRegister">
            + 새 사례 등록
          </A>
          <nav className="nav" aria-label="메뉴">
            <A to="/Main">홈</A>
            <A className="on" to="/CaseList">
              사례 관리
            </A>
            <A to="/Schedule">일정</A>
            <A to="/ChildLink">
              아이 연계<span className="cnt">4</span>
            </A>
            <A to="/Closure">
              종결 검토<span className="cnt">2</span>
            </A>
            <A to="/Stats">통계</A>
            <A to="/Settings">설정</A>
          </nav>
          <div className="me">
            <span className="av">이</span>
            <b style={{ fontWeight: '500' }}>이서연 상담원</b>
            <A to="/Login" className="note" style={{ marginLeft: 'auto' }}>
              로그아웃
            </A>
          </div>
        </aside>
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
          <nav aria-label="위치" className="note">
            <A to="/CaseList">사례 관리</A> › 이서윤 C-2026-0351
          </nav>
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '14px 18px' }}>
            <div style={{ flex: '1 1 320px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>이서윤</h1>
                <span className="sub">13세 · 중1</span>
                <span className="chip c-hi">위험도 상</span>
              </div>
              <div className="note">C-2026-0351 · 다음 상담 오늘 16:00</div>
            </div>
            <A className="btn btn-s" to="/UploadModal">
              ↑ 녹취 올리기
            </A>
          </section>
          <nav className="tabs" aria-label="사례 상세 메뉴">
            <A to="/CaseDetail">내담자 정보</A>
            <A to="/CaseHistory">상담 이력</A>
            <A to="/PreBriefing">상담 전 브리핑</A>
            <A to="/CaseApp">아이 연계</A>
            <A className="on" aria-current="page" to="/CaseDocs">
              문서함
            </A>
          </nav>
          <nav aria-label="위치" className="note" style={{ marginTop: '-8px' }}>
            <A to="/CaseDocs">문서함</A> › 기관 서식 작성
          </nav>
          <div role="tablist" aria-label="서식" style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
            {(v.tabs || []).map((t, tIndex) => (
              <Fragment key={tIndex}>
                <button
                  type="button"
                  role="tab"
                  className={`ftab ${t.cls}`}
                  aria-selected={t.on}
                  onClick={t.pick}
                >
                  {t.label}
                </button>
              </Fragment>
            ))}
          </div>
          {v.tA ? (
            <>
              <section
                className="card"
                aria-label="사정기록지 안전영역"
                style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '14px' }}
              >
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '8px' }}>
                  <h2 className="h2">사정기록지 · 안전영역</h2>
                  <span className="note">서식 6</span>
                </div>
                {(v.safety || []).map((g, gIndex) => (
                  <Fragment key={gIndex}>
                    <div className="grp">{g.name}</div>
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
                                  style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd }}
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
                <div className="grp">환경</div>
                <div className="item">
                  <span>조부모, 친구, 이웃 등 신뢰할만한 주위 사람 (Key Person)</span>
                  <span className="opt3">
                    {(v.keyOpts || []).map((o, oIndex) => (
                      <Fragment key={oIndex}>
                        <button
                          type="button"
                          onClick={o.pick}
                          style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd }}
                        >
                          {o.label}
                        </button>
                      </Fragment>
                    ))}
                  </span>
                  <span className="ev">
                    <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                      AI 제안 · 있음 (조모)
                    </span>
                    7회차(9/18) 녹취 02:40 "무서우면 할머니한테 전화할 거예요"
                  </span>
                </div>
                <div className="grp">
                  안전점수{' '}
                  <span className="note" style={{ fontWeight: '400' }}>
                    1–10점
                  </span>
                </div>
                {(v.scoreRows || []).map((r, rIndex) => (
                  <Fragment key={rIndex}>
                    <div className="item" style={{ gridTemplateColumns: '150px 110px minmax(0, 1fr)' }}>
                      <span>{r.who}</span>
                      <input
                        className="inp"
                        type="number"
                        min="1"
                        max="10"
                        placeholder="( )점"
                        aria-label={`${r.who} 안전점수`}
                        style={{ width: '100px' }}
                      />
                      <input
                        className="inp"
                        type="text"
                        placeholder="이유"
                        aria-label={`${r.who} 이유`}
                        style={{ width: '100%' }}
                      />
                    </div>
                  </Fragment>
                ))}
                <div className="grp">아동학대 위험수준별 개입 사정 척도</div>
                <div className="item" style={{ gridTemplateColumns: '1fr auto' }}>
                  <span>
                    위험요인 <b className="brn">{v.riskSum}점</b> / 보호요인{' '}
                    <b className="brn">{v.protSum}점</b> <span className="note">· {v.filled}/43 입력</span>
                  </span>
                  <button type="button" className="btn btn-sm btn-s" onClick={v.goC}>
                    척도 열기
                  </button>
                </div>
                <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <b style={{ fontSize: '14px' }}>담당자 소견</b>
                  <textarea className="ta2" placeholder="직접 작성" />
                </label>
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px' }}>
                  <b style={{ fontSize: '14px' }}>사정결과</b>
                  <span className="opt3">
                    {(v.resultOpts || []).map((o, oIndex) => (
                      <Fragment key={oIndex}>
                        <button
                          type="button"
                          onClick={o.pick}
                          style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd }}
                        >
                          {o.label}
                        </button>
                      </Fragment>
                    ))}
                  </span>
                  <span className="note">상담원 판정</span>
                </div>
              </section>
            </>
          ) : null}
          {v.tB ? (
            <>
              <section
                className="card"
                aria-label="사례관리 점검표"
                style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '14px' }}
              >
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '8px' }}>
                  <h2 className="h2">사례관리 점검표</h2>
                  <span className="note">서식 27</span>
                </div>
                <div className="fhead">
                  <div>
                    <span className="k">성명</span>
                    <span className="v">이서윤</span>
                  </div>
                  <div>
                    <span className="k">담당 상담원</span>
                    <span className="v">이서연</span>
                  </div>
                  <div>
                    <span className="k">생년월일</span>
                    <span className="v">2013-03-14 (만 13세)</span>
                  </div>
                  <div>
                    <span className="k">점검일/회차</span>
                    <span className="v">2026-10-12 / 3차</span>
                  </div>
                  <div>
                    <span className="k">점검장소</span>
                    <span className="v">
                      <input
                        className="inp"
                        type="text"
                        defaultValue="기관 면담실 B"
                        aria-label="점검장소"
                        style={{ height: '34px', width: '100%' }}
                      />
                    </span>
                  </div>
                  <div>
                    <span className="k">이전 점검일</span>
                    <span className="v">2026-09-14</span>
                  </div>
                </div>
                <div className="item note" style={{ padding: '6px 4px' }}>
                  <span>점검의 내용</span>
                  <span>예 / 아니오</span>
                </div>
                {(v.checks || []).map((c, cIndex) => (
                  <Fragment key={cIndex}>
                    <div className="item">
                      <span>{c.q}</span>
                      <span className="opt3" role="group" aria-label={c.q}>
                        {(c.opts || []).map((o, oIndex) => (
                          <Fragment key={oIndex}>
                            <button
                              type="button"
                              onClick={o.pick}
                              style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd }}
                            >
                              {o.label}
                            </button>
                          </Fragment>
                        ))}
                      </span>
                      {c.hasEv ? (
                        <>
                          <span className="ev">
                            <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                              AI 제안 · {c.ai}
                            </span>
                            {c.ev}
                          </span>
                        </>
                      ) : null}
                    </div>
                  </Fragment>
                ))}
                <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <span style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <b style={{ fontSize: '14px' }}>담당 상담원 소견</b>
                    <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                      AI 초안
                    </span>
                  </span>
                  <textarea
                    className="ta2"
                    defaultValue={
                      '8회차(10/2)에 신체 학대 진술이 새로 나왔고, 체크인 QB-E-05 응답이 "없어"에서 "1번"으로 바뀌어 학대 위험이 감소했다고 보기 어려움. 보호자 부모교육은 2회 연속 결석함.'
                    }
                  />
                </label>
                <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <span style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <b style={{ fontSize: '14px' }}>추후 계획</b>
                    <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                      AI 초안
                    </span>
                  </span>
                  <textarea
                    className="ta2"
                    defaultValue={
                      '재사정 실시 · 부모교육 일정 재조율(가정방문 시) · 등 · 팔 통증 의료 연계 여부 확인.'
                    }
                  />
                </label>
              </section>
            </>
          ) : null}
          {v.tC ? (
            <>
              <section
                className="card"
                aria-label="위험수준별 개입 사정 척도"
                style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '12px' }}
              >
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '8px' }}>
                  <h2 className="h2">아동학대 위험수준별 개입 사정 척도</h2>
                  <span className="note">참고자료 3 · 43문항 · 0~3점</span>
                </div>
                <div className="sum">
                  <div>
                    <div className="note">위험요인 (1~21)</div>
                    <b className="brn" style={{ fontSize: '24px' }}>
                      {v.riskSum}점
                    </b>
                    <span className="note"> / 63</span>
                  </div>
                  <div>
                    <div className="note">보호요인 (22~43)</div>
                    <b className="brn" style={{ fontSize: '24px' }}>
                      {v.protSum}점
                    </b>
                    <span className="note"> / 66</span>
                  </div>
                  <div>
                    <div className="note">입력</div>
                    <b style={{ fontSize: '24px' }}>{v.filled}</b>
                    <span className="note"> / 43 · 군 판정: 상담원</span>
                  </div>
                </div>
                {(v.scale || []).map((s, sIndex) => (
                  <Fragment key={sIndex}>
                    {s.head ? (
                      <>
                        <div className="grp" style={{ marginTop: '6px' }}>
                          {s.headLabel}
                        </div>
                      </>
                    ) : null}
                    <div className="sc">
                      <span className="note">{s.n}</span>
                      <span>
                        {s.q}
                        <span className="src" style={{ display: 'block' }}>
                          {s.ev}
                        </span>
                      </span>
                      <span className="opt3" role="group" aria-label={s.q}>
                        {(s.opts || []).map((o, oIndex) => (
                          <Fragment key={oIndex}>
                            <button
                              type="button"
                              onClick={o.pick}
                              style={{
                                background: o.bg,
                                color: o.fg,
                                fontWeight: o.fw,
                                boxShadow: o.bd,
                                minWidth: '36px',
                              }}
                            >
                              {o.label}
                            </button>
                          </Fragment>
                        ))}
                      </span>
                    </div>
                  </Fragment>
                ))}
              </section>
            </>
          ) : null}
          {v.tD ? (
            <>
              <section
                className="card"
                aria-label="축약형 가족관계 척도"
                style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '12px' }}
              >
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '8px' }}>
                  <h2 className="h2">축약형 가족관계 척도</h2>
                  <span className="note">참고자료 1 · 15문항</span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px' }}>
                  <span className="note">응답자</span>
                  <span className="opt3">
                    {(v.resp || []).map((o, oIndex) => (
                      <Fragment key={oIndex}>
                        <button
                          type="button"
                          onClick={o.pick}
                          style={{ background: o.bg, color: o.fg, fontWeight: o.fw, boxShadow: o.bd }}
                        >
                          {o.label}
                        </button>
                      </Fragment>
                    ))}
                  </span>
                  <span style={{ marginLeft: 'auto' }}>
                    평균{' '}
                    <b className="brn" style={{ fontSize: '20px' }}>
                      {v.famAvg}
                    </b>
                    <span className="note"> 점 · {v.famN}/15 응답</span>
                  </span>
                </div>
                <div
                  className="note"
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '38px minmax(0,1fr) auto',
                    gap: '10px',
                    padding: '0 4px',
                  }}
                >
                  <span />
                  <span />
                  <span>1 전혀 그렇지 않다 · 3 보통이다 · 5 항상 그렇다</span>
                </div>
                {(v.fam || []).map((s, sIndex) => (
                  <Fragment key={sIndex}>
                    <div className="sc">
                      <span className="note">{s.n}</span>
                      <span>{s.q}</span>
                      <span className="opt3">
                        {(s.opts || []).map((o, oIndex) => (
                          <Fragment key={oIndex}>
                            <button
                              type="button"
                              onClick={o.pick}
                              style={{
                                background: o.bg,
                                color: o.fg,
                                fontWeight: o.fw,
                                boxShadow: o.bd,
                                minWidth: '34px',
                              }}
                            >
                              {o.label}
                            </button>
                          </Fragment>
                        ))}
                      </span>
                    </div>
                  </Fragment>
                ))}
                <p className="src" style={{ margin: '0' }}>
                  출처: 양옥경(2001) · 양옥경 · 김연수(2007) 축약, 사회복지공동모금회 척도집(2017)
                </p>
              </section>
            </>
          ) : null}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
            <A className="btn btn-s" to="/CaseDocs">
              ← 문서함
            </A>
            <button type="button" className="btn btn-s" style={{ marginLeft: 'auto' }}>
              임시 저장
            </button>
            <button type="button" className="btn btn-p">
              상담원 확정
            </button>
          </div>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
