// 1 · STT 검수 (화자: 피해아동 · 사례관리대상자 · 상담원)
// 원본: I-SPOT 디자인 캔버스 보드 SttReview.dc.html (자동 변환 후 다듬어 쓰세요)
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import './SttReview.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { pct: 0, view: 'key', ok: {}, sp: {} };
  }
  componentDidMount() {
    this.timer = setInterval(() => {
      if (this.state.pct >= 100) {
        clearInterval(this.timer);
        return;
      }
      this.setState({ pct: Math.min(100, this.state.pct + 20) });
    }, 700);
  }
  componentWillUnmount() {
    clearInterval(this.timer);
  }
  renderVals() {
    const s = this.state;
    const all = [
      { t: '00:12', sp: '상담원', text: '오늘은 집에서 만나네. 요즘 어떻게 지냈어?', c: 0.97 },
      { t: '00:20', sp: '피해아동', text: '그냥… 학교는 괜찮아요.', c: 0.94 },
      { t: '00:35', sp: '상담원', text: '집에서는 어때?', c: 0.98 },
      {
        t: '00:41',
        sp: '피해아동',
        text: '아빠가 또 화났어요. 저한테 소리 지르고… 많이 때렸어요.',
        c: 0.62,
        key: true,
        hint: '"많이" / "만이" 불분명 · 00:38부터 다시 듣기',
      },
      { t: '00:58', sp: '상담원', text: '어디가 아팠는지 말해 줄 수 있어?', c: 0.96 },
      {
        t: '01:08',
        sp: '피해아동',
        text: '등이랑 팔이요. 근데 말하면 더 혼난다고 했어요.',
        c: 0.58,
        key: true,
        hint: '뒤 문장 겹침',
      },
      { t: '01:30', sp: '상담원', text: '그 말을 들었을 때 어떤 마음이었어?', c: 0.95 },
      { t: '01:36', sp: '피해아동', text: '무서웠어요.', c: 0.91, key: true },
      {
        t: '02:15',
        sp: '화자?',
        text: '밥도 안 줄 때가 있어요.',
        c: 0.7,
        key: true,
        hint: '화자 불확실 · 확인 전 근거 제외',
      },
      { t: '02:40', sp: '피해아동', text: '할머니 집에 가고 싶어요.', c: 0.89 },
      {
        t: '03:05',
        sp: '사례관리대상자',
        text: '(현관문 소리) 누구 왔어? 무슨 얘기 하는 거야?',
        c: 0.81,
        key: true,
        safe: true,
      },
      { t: '03:12', sp: '피해아동', text: '…아무것도 아니에요.', c: 0.88 },
    ].map((l, i) => ({ ...l, i, low: l.c < 0.75 }));
    const pick =
      s.view === 'all' ? all : s.view === 'low' ? all.filter((l) => l.low) : all.filter((l) => l.key);
    const SPK = ['피해아동', '상담원', '사례관리대상자', '보호자', '화자?'];
    const lines = pick.map((l) => {
      const done = !!s.ok[l.i];
      const edit = s.view !== 'key' && l.low;
      const sp = s.sp[l.i] || l.sp;
      return {
        t: l.t,
        sp,
        text: l.text,
        aria: `${l.t} 발화 고치기`,
        spFw: sp === '피해아동' ? 700 : 500,
        spFix: !!s.sp[l.i],
        nextSp: () => this.setState({ sp: { ...s.sp, [l.i]: SPK[(SPK.indexOf(sp) + 1) % SPK.length] } }),
        conf: `${Math.round(l.c * 100)}%`,
        edit,
        read: !edit,
        hint: done
          ? '확인했어요'
          : l.low
            ? l.hint || ''
            : l.safe
              ? '신변안전 · 사례관리대상자 귀가 후 아동 발화 감소'
              : '',
        hintFg: !done && !l.low && l.safe ? '#93452E' : '#6F7880',
        bg: l.low && !done && s.view !== 'key' ? '#F8F5EC' : '#FFFFFF',
        okLabel: done ? '확인됨 ✓' : '확인',
        ok: () => this.setState({ ok: { ...s.ok, [l.i]: !done } }),
      };
    });
    const lowLeft = all.filter((l) => l.low && !s.ok[l.i]).length;
    const stages = [
      '화자 구분 중',
      '전사 중',
      '신뢰도 계산 중',
      '핵심 발화 고르는 중',
      '거의 끝났어요',
      '완료',
    ];
    const titles = { key: '1차 임시 핵심 발화', all: '전체 STT', low: '저신뢰 구간' };
    return {
      analyzing: s.pct < 100,
      done: s.pct >= 100,
      pct: s.pct,
      pctW: s.pct + '%',
      stageLabel: stages[Math.floor(s.pct / 20)],
      skip: () => this.setState({ pct: 100 }),
      lines,
      lowLeft: lowLeft + '곳',
      viewTitle: titles[s.view],
      chipText: s.view === 'key' ? '임시 · 검수 전' : lowLeft ? `확인할 곳 ${lowLeft}` : '모두 확인',
      chipCls: s.view === 'key' ? 'chip c-sand' : lowLeft ? 'chip c-check' : 'chip c-ok',
      allCls: s.view === 'all' ? 'btn-p' : 'btn-s',
      lowCls: s.view === 'low' ? 'btn-p' : 'btn-s',
      showAll: () => this.setState({ view: s.view === 'all' ? 'key' : 'all' }),
      showLow: () => this.setState({ view: s.view === 'low' ? 'key' : 'low' }),
    };
  }
}

export default function SttReview(props) {
  const v = useDC(Logic, props);
  return (
    <div className="pg-SttReview">
      <div
        style={{
          minHeight: '1250px',
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
            <A className="stp on" to="/SttReview" aria-current="step">
              <span className="sn">1</span>
              <b style={{ fontWeight: '700' }}>STT 검수</b>
            </A>
            <A className="stp" to="/SignalReview">
              <span className="sn">2</span>
              <b style={{ fontWeight: '500' }}>위험 신호 검토</b>
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
          {v.analyzing ? (
            <>
              <section
                className="card"
                aria-live="polite"
                style={{ padding: '28px 26px', display: 'flex', flexDirection: 'column', gap: '12px' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span className="chip c-sky">분석 중</span>
                  <b>{v.stageLabel}</b>
                  <span className="note" style={{ marginLeft: 'auto' }}>
                    {v.pct}%
                  </span>
                </div>
                <div className="prog">
                  <span style={{ width: v.pctW }} />
                </div>
                <button
                  type="button"
                  className="btn btn-sm btn-s"
                  style={{ alignSelf: 'flex-start' }}
                  onClick={v.skip}
                >
                  완료 화면 보기
                </button>
              </section>
            </>
          ) : null}
          {v.done ? (
            <>
              <section className="card" aria-label="STT 검수" style={{ overflow: 'hidden' }}>
                <div className="hd">
                  <h2 className="h2">{v.viewTitle}</h2>
                  <span className={v.chipCls}>{v.chipText}</span>
                  <div style={{ marginLeft: 'auto', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    <button type="button" className={`btn btn-sm ${v.allCls}`} onClick={v.showAll}>
                      전체 STT 보기
                    </button>
                    <button type="button" className={`btn btn-sm ${v.lowCls}`} onClick={v.showLow}>
                      저신뢰 구간 보기 · {v.lowLeft}
                    </button>
                  </div>
                </div>
                {(v.lines || []).map((l, lIndex) => (
                  <Fragment key={lIndex}>
                    <div className="ln" style={{ background: l.bg }}>
                      <span className="note">{l.t}</span>
                      <span
                        style={{
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '2px',
                          alignItems: 'flex-start',
                        }}
                      >
                        <button
                          type="button"
                          className="chip"
                          title="눌러서 화자 바꾸기"
                          aria-label={`화자 바꾸기 · 지금 ${l.sp}`}
                          onClick={l.nextSp}
                          style={{
                            border: '0',
                            cursor: 'pointer',
                            font: 'inherit',
                            fontSize: '12px',
                            background: '#F1EFE9',
                            color: '#55606A',
                            fontWeight: l.spFw,
                          }}
                        >
                          {l.sp} ▾
                        </button>
                        {l.spFix ? (
                          <>
                            <span className="note" style={{ fontSize: '11px' }}>
                              상담원 수정
                            </span>
                          </>
                        ) : null}
                      </span>
                      <span style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {l.edit ? (
                          <>
                            <input className="in" type="text" defaultValue={l.text} aria-label={l.aria} />
                          </>
                        ) : null}
                        {l.read ? (
                          <>
                            <span style={{ fontSize: '15px' }}>{l.text}</span>
                          </>
                        ) : null}
                        <span className="note" style={{ color: l.hintFg }}>
                          {l.hint}
                        </span>
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span className="note">{l.conf}</span>
                        {l.edit ? (
                          <>
                            <button type="button" className="btn btn-sm btn-s" onClick={l.ok}>
                              {l.okLabel}
                            </button>
                          </>
                        ) : null}
                      </span>
                    </div>
                  </Fragment>
                ))}
                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '16px 22px',
                  }}
                >
                  <A className="btn btn-p" to="/SignalReview" style={{ marginLeft: 'auto' }}>
                    신호 분석 →
                  </A>
                </div>
              </section>
            </>
          ) : null}
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
