// 3 · 상담 요약 (사정 관점) · 상담 일지 (기관 양식)
// 원본: I-SPOT 디자인 캔버스 보드 NoteWrite.dc.html (자동 변환 후 다듬어 쓰세요)
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import './NoteWrite.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { tr: {}, hm: {} };
  }
  renderVals() {
    const s = this.state;
    const sums = [
      {
        k: '(안전관련) 조사 후 변화된 사항',
        v: '6회차 "맞은 적은 잘 모르겠어요"였던 진술이 8회차에 "많이 때렸어요"로 바뀜. 두 진술 모두 원문대로 남김.',
        src: '6회차 05:02 · 8회차 00:41',
      },
      {
        k: '아동안전과 관련된 강점과 자원',
        v: '조모에게 연락하는 안전 계획을 알고 있음. 할머니 집에 가고 싶다고 말함.',
        src: '7회차 02:40 · 8회차 02:40',
      },
      {
        k: '아동안전과 관련된 위험요인',
        v: '보호자(부)의 체벌과 함구 요구("말하면 더 혼난다"). 식사 관련 발화는 화자 확인 필요.',
        src: '8회차 00:41 · 01:08 · 02:15',
      },
      {
        k: '앞으로 원하는 변화 · 원하는 서비스/지원',
        v: '아동: 할머니 집에 가고 싶음. 서비스: 등 · 팔 통증 의료 확인 필요.',
        src: '8회차 02:40 · 01:08',
      },
    ];
    const T = [
      '불안',
      '낮은 자존감',
      '우울',
      '무력감',
      '대인관계 기피',
      '학교부적응',
      '애착문제',
      '주의산만',
      '반항 · 충동 · 공격성',
      '잦은 결석',
      '수면 · 위생 문제',
      '특성없음',
    ];
    const TAI = { 불안: '01:36 "무서웠어요" · 체크인 "조금 걱정돼" 2주' };
    const traits = T.map((t) => {
      const on = s.tr[t] !== undefined ? s.tr[t] : !!TAI[t];
      return {
        label: t,
        mark: on ? '✓' : '+',
        bg: on ? '#E2ECF8' : '#FFFFFF',
        bd: on ? '#A8C6E7' : '#DCD5C3',
        fg: on ? '#2E5687' : '#2F3A44',
        fw: on ? 700 : 400,
        toggle: () => this.setState({ tr: { ...s.tr, [t]: !on } }),
      };
    });
    const H = [
      '부적절한 양육태도',
      '양육지식 및 기술부족',
      '부부 및 가족갈등',
      '경제적 어려움',
      '스트레스',
      '알콜남용',
      '사회적 고립',
      '배우자폭력',
      '특성없음',
    ];
    const HAI = { '부적절한 양육태도': '00:41 체벌 진술 · 01:08 함구 요구' };
    const homes = H.map((t) => {
      const on = s.hm[t] !== undefined ? s.hm[t] : !!HAI[t];
      return {
        label: t,
        mark: on ? '✓' : '+',
        bg: on ? '#E2ECF8' : '#FFFFFF',
        bd: on ? '#A8C6E7' : '#DCD5C3',
        fg: on ? '#2E5687' : '#2F3A44',
        fw: on ? 700 : 400,
        toggle: () => this.setState({ hm: { ...s.hm, [t]: !on } }),
      };
    });
    return {
      sums,
      traits,
      homes,
      traitEv: Object.keys(TAI).map((k) => ({ label: k, ev: TAI[k] })),
      homeEv: Object.keys(HAI).map((k) => ({ label: k, ev: HAI[k] })),
    };
  }
}

export default function NoteWrite(props) {
  const v = useDC(Logic, props);
  return (
    <div className="pg-NoteWrite">
      <div
        style={{
          minHeight: '2000px',
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
            <A to="/CaseList">사례 관리</A> › <A to="/CaseDetail">이서윤 C-2026-0351</A> ›{' '}
            <A to="/CaseHistory">상담 이력</A> › <A to="/SessionDetail">8회차</A>
          </nav>
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 280px' }}>
              <div className="sub">10/2(금) 방문상담</div>
              <h1 style={{ margin: '2px 0 0', fontSize: '28px', fontWeight: '700' }}>8회차 처리 · 이서윤</h1>
            </div>
          </header>
          <nav className="steps" aria-label="회차 처리 단계">
            <A className="stp done" to="/SttReview">
              <span className="sn">✓</span>
              <b style={{ fontWeight: '500' }}>STT 검수</b>
            </A>
            <A className="stp done" to="/SignalReview">
              <span className="sn">✓</span>
              <b style={{ fontWeight: '500' }}>위험 신호 검토</b>
            </A>
            <A className="stp on" to="/NoteWrite" aria-current="step">
              <span className="sn">3</span>
              <b style={{ fontWeight: '700' }}>요약 · 일지 작성</b>
            </A>
            <A className="stp" to="/FollowupQ">
              <span className="sn">4</span>
              <b style={{ fontWeight: '500' }}>추가 확인 · 질문</b>
            </A>
          </nav>
          <section
            className="card"
            aria-label="상담 요약"
            style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '14px' }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
              <h2 className="h2">상담 요약</h2>
              <span className="chip c-ai">AI 초안</span>
            </div>
            {(v.sums || []).map((r, rIndex) => (
              <Fragment key={rIndex}>
                <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <span style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
                    <b style={{ fontSize: '14px' }}>{r.k}</b>
                    <span className="ev" style={{ fontSize: '12px' }}>
                      근거 · {r.src}
                    </span>
                  </span>
                  <textarea className="ta2" aria-label={r.k} defaultValue={r.v} />
                </label>
              </Fragment>
            ))}
          </section>
          <section
            className="card"
            aria-label="상담 일지"
            style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '14px' }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
              <h2 className="h2">상담 일지 · 서비스제공 일지</h2>
              <span className="chip c-ai">AI 초안 · 기관 양식</span>
            </div>
            <div className="fhead">
              <div>
                <span className="k">사건번호</span>
                <span className="v">C-2026-0351</span>
              </div>
              <div>
                <span className="k">대상아동</span>
                <span className="v">이서윤 (여, 만 13세)</span>
              </div>
              <div>
                <span className="k">상담일시</span>
                <span className="v">2026-10-02(금) 15:00~15:24</span>
              </div>
              <div>
                <span className="k">장소 · 유형</span>
                <span className="v">가정방문 · 정기상담 8회차</span>
              </div>
              <div>
                <span className="k">면접대상자/관계</span>
                <span className="v">이서윤 / 피해아동</span>
              </div>
              <div>
                <span className="k">담당 상담원</span>
                <span className="v">이서연</span>
              </div>
            </div>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <b style={{ fontSize: '14px' }}>아동 진술</b>
              <textarea
                className="ta2"
                style={{ minHeight: '104px' }}
                defaultValue={
                  '· 00:41 "아빠가 또 화났어요. 저한테 소리 지르고… 많이 때렸어요"\n· 01:08 "등이랑 팔이요. 근데 말하면 더 혼난다고 했어요"\n· 01:36 "무서웠어요"'
                }
              />
            </label>
            <div className="grp">대상자 태도 및 관찰내용</div>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <b style={{ fontSize: '14px' }}>(대상자 태도)</b>
                <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                  AI 초안 · 녹취에서
                </span>
              </span>
              <textarea
                className="ta2"
                defaultValue={
                  '00:41 발화 전 약 4초 침묵 후 작은 목소리로 답함. 후반부(02:40) 할머니 이야기에서 목소리가 밝아짐. 03:05 사례관리대상자(부) 귀가 후 아동 발화가 줄어듦.'
                }
              />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <b style={{ fontSize: '14px' }}>(물리적 환경)</b>
              <textarea className="ta2" placeholder="상담원 작성" />
              <span className="note acc">신변안전 · 기관 복귀 후 기록 (현장 기록 금지)</span>
            </label>
            <div className="grp">아동 특성</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {(v.traits || []).map((t, tIndex) => (
                <Fragment key={tIndex}>
                  <button
                    type="button"
                    className="chipck"
                    onClick={t.toggle}
                    style={{ background: t.bg, borderColor: t.bd, color: t.fg, fontWeight: t.fw }}
                  >
                    {t.mark} {t.label}
                  </button>
                </Fragment>
              ))}
            </div>
            {(v.traitEv || []).map((e, eIndex) => (
              <Fragment key={eIndex}>
                <span className="ev">
                  <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                    AI 제안 · {e.label}
                  </span>
                  {e.ev}
                </span>
              </Fragment>
            ))}
            <div className="grp">가정상황</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {(v.homes || []).map((t, tIndex) => (
                <Fragment key={tIndex}>
                  <button
                    type="button"
                    className="chipck"
                    onClick={t.toggle}
                    style={{ background: t.bg, borderColor: t.bd, color: t.fg, fontWeight: t.fw }}
                  >
                    {t.mark} {t.label}
                  </button>
                </Fragment>
              ))}
            </div>
            {(v.homeEv || []).map((e, eIndex) => (
              <Fragment key={eIndex}>
                <span className="ev">
                  <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                    AI 제안 · {e.label}
                  </span>
                  {e.ev}
                </span>
              </Fragment>
            ))}
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <b style={{ fontSize: '14px' }}>위험 신호 검토 결과</b>
              <textarea
                className="ta2"
                defaultValue={
                  '채택: 직접 신체 가해(00:41) · 상해 부위 진술(01:08) · 위협 · 공포 유발(01:08, 01:36)\n보류: 기본 보호 · 양육 방임(02:15, 화자 불확실)'
                }
              />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <b style={{ fontSize: '14px' }}>상담원 소견 및 향후 계획</b>
                <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                  AI 초안
                </span>
              </span>
              <textarea
                className="ta2"
                style={{ minHeight: '96px' }}
                defaultValue={
                  '신체 학대 진술이 새로 나와 재사정이 필요함. 9회차에 등 · 팔 통증 치료 여부와 02:15 발화 화자를 확인할 예정. 보호자 동석 시 아동 발화가 줄어 다음 상담은 기관 면담실에서 진행함.'
                }
              />
            </label>
          </section>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
            <A className="btn btn-s" to="/SignalReview">
              ← 위험 신호 검토
            </A>
            <A className="btn btn-p" to="/FollowupQ" style={{ marginLeft: 'auto' }}>
              저장 · 추가 확인 · 질문 →
            </A>
          </div>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
