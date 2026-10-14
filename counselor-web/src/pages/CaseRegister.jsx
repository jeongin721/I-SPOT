// 새 사례 등록 (팝업 · 서식 4 초기면접지)
// 원본: 다솔 님 디자인 counselor-web-design/CaseRegister.dc.html (front_new 브랜치). 화면 값은 아직 예시(가상) 데이터다.
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import './CaseRegister.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { tab: 'A', ty: {}, hm: {}, tr: {}, fam: '', rows: 2 };
  }
  renderVals() {
    const s = this.state;
    const on = (v) => ({
      bg: v ? '#F1EADA' : '#FFFFFF',
      bd: v ? '#2B2A26' : '#DAD5C9',
      fg: v ? '#2B2A26' : '#2B2A26',
      fw: v ? 700 : 400,
      mark: v ? '✓' : '+',
    });
    const multi = (list, key) =>
      list.map((label) => {
        const v = !!s[key][label];
        return { label, ...on(v), toggle: () => this.setState({ [key]: { ...s[key], [label]: !v } }) };
      });
    const TY = ['방임', '신체학대', '정서학대', '성학대'];
    const HM = [
      '성격 및 기질 문제',
      '어릴적 학대경험',
      '알콜남용',
      '약물남용',
      '신체질환 및 장애',
      '정신질환 및 장애',
      '원치않은 아동',
      '부적절한 양육태도',
      '양육지식 및 기술부족',
      '부부 및 가족갈등',
      '성문제',
      '스트레스',
      '사회적 고립',
      '경제적 어려움',
      '배우자폭력',
      '존속학대',
      '전과력',
      '종교문제',
      '도박 · 게임중독',
      '특성없음',
      '기타',
    ];
    const FAM = [
      '일반가정',
      '부자가정',
      '모자가정',
      '미혼부 · 모 가정',
      '친부+계모',
      '친모+계부',
      '친인척보호',
      '친부+동거녀',
      '친모+동거남',
      '가정위탁',
      '입양가정',
      '시설보호',
      '기타',
    ];
    const TR = [
      '거짓말',
      '반항 · 충동 · 공격성',
      '도벽',
      '가출',
      '약물',
      '흡연',
      '음주',
      '인터넷(게임)중독',
      '성문제',
      '주의산만',
      '과잉행동',
      '늦은귀가',
      '불건전한 또래관계',
      '대인관계 기피',
      '학교부적응',
      '잦은결석',
      '학교폭력 가해자',
      '학교폭력 피해자',
      '불안',
      '애착문제',
      '무력감',
      '우울',
      '낮은자존감',
      '신체발달지연',
      '언어문제',
      '학습문제',
      '대소변문제',
      '성격 및 기질문제',
      '위생문제',
      '틱',
      '급(만)성질병',
      '영양결핍',
      '탐식 및 결식',
      '특성없음',
      '기타',
    ];
    const fams = FAM.map((label) => ({
      label,
      ...on(s.fam === label),
      pick: () => this.setState({ fam: s.fam === label ? '' : label }),
    }));
    const tabs = [
      ['A', '① 기본 정보 (필수)'],
      ['B', '② 초기면접 내용'],
    ].map(([k, label]) => ({
      label,
      sel: s.tab === k ? 'true' : 'false',
      bd: s.tab === k ? '#C2A36B' : 'transparent',
      fg: s.tab === k ? '#2B2A26' : '#66625A',
      fw: s.tab === k ? 700 : 400,
      go: () => this.setState({ tab: k }),
    }));
    return {
      tabs,
      isA: s.tab === 'A',
      isB: s.tab === 'B',
      types: multi(TY, 'ty'),
      homes: multi(HM, 'hm'),
      traits: multi(TR, 'tr'),
      fams,
      famRows: Array.from({ length: s.rows }, (_, i) => i),
      addRow: () => this.setState({ rows: s.rows + 1 }),
      midLabel: s.tab === 'A' ? '초기면접 내용 →' : '← 기본 정보',
      goB: () => this.setState({ tab: s.tab === 'A' ? 'B' : 'A' }),
    };
  }
}

export default function CaseRegister(props) {
  const theme = useTheme();
  const v = useDC(Logic, props);
  return (
    <div className="pg-CaseRegister">
      <div
        className={theme.cls}
        style={{
          minHeight: '1700px',
          background: 'rgba(47,58,68,0.40)',
          fontFamily: "'IBM Plex Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          color: '#2B2A26',
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'center',
          padding: '48px 16px',
          position: 'relative',
        }}
      >
        <div className="thm-abs">
          <ThemeToggle />
        </div>
        <section
          role="dialog"
          aria-modal="true"
          aria-labelledby="reg-title"
          style={{
            width: '100%',
            maxWidth: '860px',
            background: '#FFFFFF',
            borderRadius: '24px',
            boxShadow: '0 20px 60px rgba(43, 42, 38,0.22)',
            overflow: 'hidden',
          }}
        >
          <div style={{ padding: '24px 30px 0', display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
            <div>
              <h1 id="reg-title" style={{ margin: '0', fontSize: '20px', fontWeight: '700' }}>
                새 사례 등록
              </h1>
              <div className="note">초기면접지(아동용) · 서식 4</div>
            </div>
            <A
              to="/CaseList"
              aria-label="닫기"
              style={{
                marginLeft: 'auto',
                width: '40px',
                height: '40px',
                borderRadius: '50%',
                background: '#F7F6F2',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                textDecoration: 'none',
                color: '#2B2A26',
                fontSize: '18px',
              }}
            >
              ×
            </A>
          </div>
          <div role="tablist" style={{ display: 'flex', margin: '16px 30px 0', borderBottom: '1px solid #EAE7DF' }}>
            {(v.tabs || []).map((t, tIndex) => (
              <Fragment key={tIndex}>
                <button
                  type="button"
                  role="tab"
                  className="tabb"
                  aria-selected={t.sel}
                  onClick={t.go}
                  style={{ borderBottomColor: t.bd, color: t.fg, fontWeight: t.fw }}
                >
                  {t.label}
                </button>
              </Fragment>
            ))}
          </div>

          <form style={{ padding: '22px 30px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
            {v.isA ? (
              <>
                <div className="g3">
                  <label className="fl">
                    <span className="lb">
                      신고접수일 <span className="req">*</span>
                    </span>
                    <input className="inp" type="date" defaultValue="2026-10-12" />
                  </label>
                  <label className="fl">
                    <span className="lb">
                      사례연계일 <span className="req">*</span>
                    </span>
                    <input className="inp" type="date" defaultValue="2026-10-12" />
                  </label>
                  <label className="fl">
                    <span className="lb">최초면접일</span>
                    <input className="inp" type="date" />
                  </label>
                  <label className="fl">
                    <span className="lb">
                      개별사건번호 <span className="req">*</span>
                    </span>
                    <input className="inp" type="text" defaultValue="C-2026-0352" />
                  </label>
                  <label className="fl">
                    <span className="lb">
                      대상아동 이름 <span className="req">*</span>
                    </span>
                    <input className="inp" type="text" placeholder="이름" />
                  </label>
                  <label className="fl">
                    <span className="lb">
                      성별 <span className="req">*</span>
                    </span>
                    <select className="inp">
                      <option>선택</option>
                      <option>여</option>
                      <option>남</option>
                    </select>
                  </label>
                  <label className="fl">
                    <span className="lb">
                      생년월일 (나이) <span className="req">*</span>
                    </span>
                    <input className="inp" type="date" />
                  </label>
                  <label className="fl">
                    <span className="lb">
                      사례관리대상자 <span className="req">*</span>
                    </span>
                    <input className="inp" type="text" placeholder="이름" />
                  </label>
                  <label className="fl">
                    <span className="lb">
                      관계 <span className="req">*</span>
                    </span>
                    <select className="inp">
                      <option>선택</option>
                      <option>친부</option>
                      <option>친모</option>
                      <option>계부</option>
                      <option>계모</option>
                      <option>조부모</option>
                      <option>친인척</option>
                      <option>기타</option>
                    </select>
                  </label>
                </div>

                <div className="fl">
                  <span className="lb">
                    학대유형 <span className="req">*</span>{' '}
                    <span className="note" style={{ fontWeight: '400' }}>
                      복수 선택
                    </span>
                  </span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {(v.types || []).map((o, oIndex) => (
                      <Fragment key={oIndex}>
                        <button
                          type="button"
                          className="pk"
                          onClick={o.toggle}
                          style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}
                        >
                          {o.mark} {o.label}
                        </button>
                      </Fragment>
                    ))}
                  </div>
                </div>

                <div className="g3">
                  <label className="fl">
                    <span className="lb">
                      조치결과 · 피해아동 <span className="req">*</span>
                    </span>
                    <select className="inp">
                      <option>원가정보호</option>
                      <option>친인척보호</option>
                      <option>연고자에 의한 보호</option>
                      <option>가정위탁</option>
                      <option>시설입소</option>
                      <option>병원입원</option>
                      <option>기타</option>
                    </select>
                  </label>
                  <label className="fl">
                    <span className="lb">
                      조치결과 · 사례관리대상자 <span className="req">*</span>
                    </span>
                    <select className="inp">
                      <option>지속관찰</option>
                      <option>아동과의 분리</option>
                      <option>고소 · 고발</option>
                      <option>기타</option>
                    </select>
                  </label>
                  <label className="fl">
                    <span className="lb">면접대상자 / 관계</span>
                    <input className="inp" type="text" placeholder="예: 이서윤 / 피해아동" />
                  </label>
                  <label className="fl">
                    <span className="lb">담당 상담원</span>
                    <input className="inp" type="text" defaultValue="이서연" />
                  </label>
                  <label className="fl">
                    <span className="lb">위험도 (우선)</span>
                    <select className="inp">
                      <option>선택</option>
                      <option>상</option>
                      <option>중</option>
                      <option>하</option>
                    </select>
                  </label>
                </div>
                <label className="fl">
                  <span className="lb">
                    사례연계 경위 <span className="req">*</span>
                  </span>
                  <textarea className="ta2" placeholder="신고 경위 · 신고자 유형 · 연계 내용"></textarea>
                </label>
              </>
            ) : null}

            {v.isB ? (
              <>
                <div className="sec">
                  가정상황{' '}
                  <span className="note" style={{ fontWeight: '400' }}>
                    (복수응답 가능)
                  </span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {(v.homes || []).map((o, oIndex) => (
                    <Fragment key={oIndex}>
                      <button
                        type="button"
                        className="pk"
                        onClick={o.toggle}
                        style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}
                      >
                        {o.mark} {o.label}
                      </button>
                    </Fragment>
                  ))}
                </div>
                <label className="fl">
                  <span className="lb">보호자와 아동과의 관계</span>
                  <textarea className="ta2"></textarea>
                </label>

                <div className="sec">가족유형</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {(v.fams || []).map((o, oIndex) => (
                    <Fragment key={oIndex}>
                      <button
                        type="button"
                        className="pk"
                        onClick={o.pick}
                        style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}
                      >
                        {o.label}
                      </button>
                    </Fragment>
                  ))}
                </div>

                <div className="sec">가족관계</div>
                <div style={{ overflowX: 'auto' }}>
                  <table className="ft">
                    <thead>
                      <tr>
                        <th>성명</th>
                        <th>관계</th>
                        <th>나이</th>
                        <th>종교</th>
                        <th>학력</th>
                        <th>직업</th>
                        <th>동거여부</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(v.famRows || []).map((r, rIndex) => (
                        <Fragment key={rIndex}>
                          <tr>
                            <td>
                              <input aria-label="성명" />
                            </td>
                            <td>
                              <input aria-label="관계" />
                            </td>
                            <td>
                              <input aria-label="나이" />
                            </td>
                            <td>
                              <input aria-label="종교" />
                            </td>
                            <td>
                              <input aria-label="학력" />
                            </td>
                            <td>
                              <input aria-label="직업" />
                            </td>
                            <td>
                              <input aria-label="동거여부" />
                            </td>
                          </tr>
                        </Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
                <button
                  type="button"
                  className="btn btn-sm btn-s"
                  style={{ alignSelf: 'flex-start' }}
                  onClick={v.addRow}
                >
                  + 가족 추가
                </button>

                <div className="sec">
                  아동 특성{' '}
                  <span className="note" style={{ fontWeight: '400' }}>
                    (복수응답 가능)
                  </span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {(v.traits || []).map((o, oIndex) => (
                    <Fragment key={oIndex}>
                      <button
                        type="button"
                        className="pk"
                        onClick={o.toggle}
                        style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}
                      >
                        {o.mark} {o.label}
                      </button>
                    </Fragment>
                  ))}
                </div>

                <div className="sec">문제력 · 건강정도</div>
                <div className="g3">
                  <label className="fl">
                    <span className="lb">현 상황</span>
                    <textarea className="ta2"></textarea>
                  </label>
                  <label className="fl">
                    <span className="lb">이유 인식</span>
                    <textarea className="ta2"></textarea>
                  </label>
                </div>
                <div className="g3">
                  <label className="fl">
                    <span className="lb">질병</span>
                    <input className="inp" type="text" />
                  </label>
                  <label className="fl">
                    <span className="lb">장애</span>
                    <input className="inp" type="text" />
                  </label>
                  <label className="fl">
                    <span className="lb">병원치료</span>
                    <input className="inp" type="text" />
                  </label>
                  <label className="fl">
                    <span className="lb">정신과 진단</span>
                    <input className="inp" type="text" />
                  </label>
                  <label className="fl">
                    <span className="lb">타기관 상담</span>
                    <input className="inp" type="text" />
                  </label>
                </div>

                <div className="sec">대상자 태도 및 관찰내용</div>
                <div className="g3">
                  <label className="fl">
                    <span className="lb">대상자 태도</span>
                    <textarea className="ta2"></textarea>
                  </label>
                  <label className="fl">
                    <span className="lb">물리적 환경</span>
                    <textarea className="ta2"></textarea>
                  </label>
                </div>
                <label className="fl">
                  <span className="lb">상담원 소견 및 향후 계획</span>
                  <textarea className="ta2" style={{ minHeight: '96px' }}></textarea>
                </label>
              </>
            ) : null}

            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                justifyContent: 'flex-end',
                gap: '10px',
                borderTop: '1px solid #EAE7DF',
                paddingTop: '18px',
              }}
            >
              <A className="btn btn-s" to="/CaseList">
                취소
              </A>
              <button type="button" className="btn btn-s" onClick={v.goB}>
                {v.midLabel}
              </button>
              <A className="btn btn-p" to="/CaseDetail">
                등록
              </A>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}
