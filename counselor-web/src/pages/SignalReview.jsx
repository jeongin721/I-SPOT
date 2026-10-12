// 2 · 위험 신호 검토
// 원본: I-SPOT 디자인 캔버스 보드 SignalReview.dc.html (자동 변환 후 다듬어 쓰세요)
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { dec: { 0: 'adopt', 1: 'adopt', 2: 'adopt', 3: 'hold' } };
  }
  renderVals() {
    const s = this.state;
    const defs = [
      {
        type: '신체',
        title: '직접 신체 가해',
        at: '00:41',
        quote: '저한테 소리 지르고… 많이 때렸어요',
        why: '보호자가 아동을 때렸다는 1인칭 진술 (세부 신호 3)',
        check: '원문 일치 ✓',
        ok: true,
      },
      {
        type: '신체',
        title: '상해 부위 진술',
        at: '01:08',
        quote: '등이랑 팔이요',
        why: '맞은 부위를 구체적으로 말함 (세부 신호 4)',
        check: '원문 일치 ✓',
        ok: true,
      },
      {
        type: '정서',
        title: '위협 · 공포 유발',
        at: '01:08 · 01:36',
        quote: '말하면 더 혼난다고 했어요 / 무서웠어요',
        why: '함구 요구와 두려움 표현이 이어짐 (세부 신호 9)',
        check: '원문 일치 ✓ · 발화별 보관',
        ok: true,
      },
      {
        type: '방임',
        title: '기본 보호 · 양육 방임',
        at: '02:15',
        quote: '밥도 안 줄 때가 있어요',
        why: '식사 제공 결핍 진술 (세부 신호 12)',
        check: '화자 불확실 · 보류 권장',
        ok: false,
      },
    ];
    const sigs = defs.map((g, i) => {
      const d = s.dec[i];
      const set = (v) => () => this.setState({ dec: { ...s.dec, [i]: v } });
      const st =
        d === 'adopt'
          ? ['채택', 'chip c-ok', 'inset 4px 0 0 #A8C6E7']
          : d === 'hold'
            ? ['보류', 'chip c-check', 'none']
            : ['제외', 'chip c-normal', 'none'];
      return {
        ...g,
        st: st[0],
        stCls: st[1],
        bar: st[2],
        aCls: d === 'adopt' ? 'on' : '',
        hCls: d === 'hold' ? 'on' : '',
        dCls: d === 'drop' ? 'on' : '',
        adopt: set('adopt'),
        hold: set('hold'),
        drop: set('drop'),
      };
    });
    const v = Object.values(s.dec);
    return {
      sigs,
      nA: v.filter((x) => x === 'adopt').length,
      nH: v.filter((x) => x === 'hold').length,
      nD: v.filter((x) => x === 'drop').length,
    };
  }
}

export default function SignalReview(props) {
  const v = useDC(Logic, props);
  return (
    <div className="pg-SignalReview">
      <div
        style={{
          minHeight: '1350px',
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
            <A className="stp on" to="/SignalReview" aria-current="step">
              <span className="sn">2</span>
              <b style={{ fontWeight: '700' }}>위험 신호 검토</b>
            </A>
            <A className="stp" to="/NoteWrite">
              <span className="sn">3</span>
              <b style={{ fontWeight: '500' }}>요약 · 일지 작성</b>
            </A>
            <A className="stp" to="/FollowupQ">
              <span className="sn">4</span>
              <b style={{ fontWeight: '500' }}>추가 확인 · 질문</b>
            </A>
          </nav>
          <section style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
            <span className="chip c-ai">AI 분석 · 판정 아님</span>
            <span style={{ marginLeft: 'auto', display: 'flex', gap: '6px' }}>
              <span className="chip c-ok">채택 {v.nA}</span>
              <span className="chip c-check">보류 {v.nH}</span>
              <span className="chip c-normal">제외 {v.nD}</span>
            </span>
          </section>
          {(v.sigs || []).map((g, gIndex) => (
            <Fragment key={gIndex}>
              <section
                className="card"
                style={{
                  padding: '18px 22px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                  boxShadow: g.bar,
                }}
              >
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                  <span className="chip c-normal">{g.type} 학대</span>
                  <b style={{ fontSize: '16px' }}>{g.title}</b>
                  <span className={g.stCls}>{g.st}</span>
                  <span role="group" aria-label="검토" className="seg" style={{ marginLeft: 'auto' }}>
                    <button type="button" className={g.aCls} onClick={g.adopt}>
                      채택
                    </button>
                    <button type="button" className={g.hCls} onClick={g.hold}>
                      보류
                    </button>
                    <button type="button" className={g.dCls} onClick={g.drop}>
                      제외
                    </button>
                  </span>
                </div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                    gap: '10px',
                  }}
                >
                  <div style={{ padding: '12px 14px', borderRadius: '12px', background: '#F8F5EC' }}>
                    <div className="note">발화 · {g.at}</div>
                    <div style={{ fontSize: '15px' }}>"{g.quote}"</div>
                  </div>
                  <div style={{ padding: '12px 14px', borderRadius: '12px', background: '#F8F5EC' }}>
                    <div className="note">근거</div>
                    <div style={{ fontSize: '13px' }}>{g.why}</div>
                    <div className="note">{g.check}</div>
                  </div>
                </div>
              </section>
            </Fragment>
          ))}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
            <A className="btn btn-s" to="/SttReview">
              ← STT 검수
            </A>
            <A className="btn btn-p" to="/NoteWrite" style={{ marginLeft: 'auto' }}>
              요약 · 일지 작성 →
            </A>
          </div>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
