// 탭 2 · 상담 이력 (① 지금까지 상담 → ② 상담 회차 → ③ 회차별 세부 신호)
// 원본: I-SPOT 디자인 캔버스 보드 CaseHistory.dc.html (자동 변환 후 다듬어 쓰세요)
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import './CaseHistory.css';

class Logic extends DCLogic {
  renderVals() {
    const RAW = {
      8: {
        date: '2026-10-02',
        kind: '방문상담 · 24분',
        status: '처리 중',
        st: 'chip c-check',
        sig: '채택 3 · 보류 1',
        proc: true,
        sttState: '검수 중 · 저신뢰 3곳',
        sttCls: 'chip c-check',
        lines: [
          { t: '00:41', sp: '아동', s: '아빠가 또 화났어요. 저한테 소리 지르고… 많이 때렸어요.', c: '62%' },
          { t: '01:08', sp: '아동', s: '등이랑 팔이요. 근데 말하면 더 혼난다고 했어요.', c: '58%' },
          { t: '01:36', sp: '아동', s: '무서웠어요.', c: '91%' },
          { t: '02:15', sp: '화자?', s: '밥도 안 줄 때가 있어요.', c: '70%' },
        ],
        diaryState: '작성 전',
        diaryCls: 'chip c-check',
        diary: '아직 작성하지 않았어요. 회차 처리 3단계에서 AI 초안을 받아 작성해요.',
        diaryBtn: '요약 · 일지 작성하러 가기',
        sumState: '작성 전',
        sumCls: 'chip c-check',
        summary: '요약은 회차 처리 3단계에서 확정돼요.',
        ai: '아동이 가정 내 상황에 대한 불안감을 표현하였으며 신체적 증상(등 · 팔 통증)을 호소함. 보호자에게서 "말하면 더 혼난다"는 말을 들었다고 진술함. 식사 관련 발화는 화자 확인 필요.',
        sigs: [
          ['신체', '직접 신체 가해 · 00:41'],
          ['신체', '상해 부위 진술 · 01:08'],
          ['정서', '위협 · 공포 유발 · 01:08, 01:36'],
          ['방임', '기본 보호 · 양육 (보류) · 02:15'],
        ],
      },
      7: {
        date: '2026-09-18',
        kind: '정기상담 · 50분',
        status: '확정',
        st: 'chip c-ok',
        sig: '채택 2',
        proc: false,
        sttState: '검수 완료',
        sttCls: 'chip c-ok',
        lines: [
          { t: '02:40', sp: '아동', s: '무서우면 할머니한테 전화할 거예요.', c: '93%' },
          { t: '05:10', sp: '아동', s: '아빠가 그 얘기 하지 말랬어요.', c: '88%' },
        ],
        diaryState: '확정',
        diaryCls: 'chip c-ok',
        diary:
          '안전 계획을 아동과 함께 정리함. 위급 시 조모에게 연락하기로 함. 보호자가 상담 내용을 말하지 말라고 했다는 진술이 있어 진술 압박 여부를 계속 확인하기로 함.',
        diaryBtn: '일지 수정',
        sumState: '확정',
        sumCls: 'chip c-ok',
        summary: '안전 계획 수립 · 진술 압박 진술 1건 · 조모 연락 체계 확인.',
        ai: '아동과 안전 계획을 수립함. 보호자의 함구 요구 정황이 확인됨.',
        sigs: [
          ['정서', '위협 · 공포 유발 · 05:10'],
          ['정서', '진술 압박 · 05:10'],
        ],
      },
      6: {
        date: '2026-09-04',
        kind: '정기상담 · 45분',
        status: '확정',
        st: 'chip c-ok',
        sig: '채택 2',
        proc: false,
        sttState: '검수 완료',
        sttCls: 'chip c-ok',
        lines: [
          { t: '03:20', sp: '아동', s: '아빠가 소리 지르는 게 제일 싫어요.', c: '95%' },
          { t: '05:02', sp: '아동', s: '맞은 적은… 잘 모르겠어요.', c: '90%' },
        ],
        diaryState: '확정',
        diaryCls: 'chip c-ok',
        diary:
          '아버지의 고성에 대한 두려움을 표현함. 신체 체벌 질문에는 "잘 모르겠다"고 답함. 진술 변화를 기록해 둠.',
        diaryBtn: '일지 수정',
        sumState: '확정',
        sumCls: 'chip c-ok',
        summary: '고성에 대한 두려움 · 체벌 질문에 모호한 답.',
        ai: '아동이 보호자의 고성에 두려움을 표현함.',
        sigs: [
          ['신체', '직접 신체 가해 · 05:02'],
          ['정서', '위협 · 공포 유발 · 03:20'],
        ],
      },
    };
    const DATES = ['', '2026-07-31', '2026-08-07', '2026-08-14', '2026-08-21', '2026-08-28'];
    const getS = (n) =>
      RAW[n] || {
        date: DATES[n],
        kind: n === 1 ? '초기면담 · 40분' : '정기상담 · 45분',
        status: '확정',
        st: 'chip c-ok',
        proc: false,
        sig: n <= 3 ? '신호 없음' : '채택 ' + (n === 5 ? 3 : 1),
        sttState: '검수 완료',
        sttCls: 'chip c-ok',
        lines: [
          {
            t: '01:00',
            sp: '아동',
            s: n <= 3 ? '친구들이랑은 잘 지내요.' : '아빠가 밀어서 넘어진 적 있어요.',
            c: '94%',
          },
        ],
        diaryState: '확정',
        diaryCls: 'chip c-ok',
        diary:
          n <= 3
            ? '관계 형성 단계. 학교생활과 교우관계를 중심으로 대화함.'
            : '가정 내 체벌 경험을 처음 진술함. 진술 내용을 원문 그대로 기록함.',
        diaryBtn: '일지 수정',
        sumState: '확정',
        sumCls: 'chip c-ok',
        summary: n <= 3 ? '관계 형성 · 학교생활 중심.' : '가정 내 체벌 진술 · 원문 기록.',
        ai: n <= 3 ? '아동과 라포 형성 중. 특이 진술 없음.' : '아동이 보호자의 밀침 경험을 진술함.',
        sigs: n <= 3 ? [] : [['신체', '직접 신체 가해 · 01:00']],
      };

    const sigs = [
      { type: '신체', name: '직접 신체 가해', v: [0, 0, 0, 1, 2, 1, 0, 1] },
      { type: '신체', name: '상해 부위 진술', v: [0, 0, 0, 0, 1, 0, 0, 1] },
      { type: '정서', name: '위협 · 공포 유발', v: [0, 0, 0, 0, 0, 1, 1, 2] },
      { type: '정서', name: '진술 압박', v: [0, 0, 0, 0, 0, 0, 1, 0] },
      { type: '방임', name: '기본 보호 · 양육', v: [0, 0, 0, 0, 0, 0, 0, -1] },
    ];
    const mrows = sigs.map((g) => ({
      type: g.type,
      name: g.name,
      cells: g.v.map((n, i) => ({
        v: n > 0 ? String(n) : n < 0 ? '?' : '',
        tip: `${i + 1}회차 · ${g.name} · ${n > 0 ? n + '번' : n < 0 ? '보류' : '없음'}`,
        bg: n >= 2 ? '#6F7880' : n === 1 ? '#EEE8DA' : 'transparent',
        fg: n >= 2 ? '#FFFFFF' : n < 0 ? '#6F7880' : '#2F3A44',
        ring: n < 0 ? 'inset 0 0 0 1.5px #6F7880' : 'none',
      })),
    }));
    const sessions = [8, 7, 6, 5, 4, 3, 2, 1].map((n) => {
      const r = getS(n);
      return { no: n + '회차', date: r.date, kind: r.kind, status: r.status, st: r.st, sig: r.sig };
    });
    return { mrows, sessions, cols: [1, 2, 3, 4, 5, 6, 7, 8].map((n) => n + '회') };
  }
}

export default function CaseHistory(props) {
  const v = useDC(Logic, props);
  return (
    <div className="pg-CaseHistory">
      <div
        style={{
          minHeight: '1550px',
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
            <A className="on" aria-current="page" to="/CaseHistory">
              상담 이력
            </A>
            <A to="/PreBriefing">상담 전 브리핑</A>
            <A to="/CaseApp">아이 연계</A>
            <A to="/CaseDocs">문서함</A>
          </nav>
          <section className="card" aria-label="지금까지 상담" style={{ padding: '24px 26px' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px 12px' }}>
              <span className="secno">1</span>
              <h2 className="h2">지금까지 상담</h2>
              <span className="chip c-ai">AI 분석 · 1~8회차</span>
              <span className="src" style={{ marginLeft: 'auto' }}>
                근거 · 확정 일지 · 검수본 · 체크인
              </span>
            </div>
            <div
              style={{
                marginTop: '16px',
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: '12px',
              }}
            >
              <div className="box">
                <div className="note">1~3회차</div>
                <b style={{ fontWeight: '500' }}>관계 형성 · 학교생활</b>
              </div>
              <div className="box">
                <div className="note">4~6회차</div>
                <b style={{ fontWeight: '500' }}>가정 내 체벌 경험</b>
                <div className="note">때림 · 밀침 첫 진술</div>
              </div>
              <div className="box">
                <div className="note">7~8회차 · 최근</div>
                <b style={{ fontWeight: '500' }}>두려움 · 보호자 관계</b>
                <div className="note">"말하면 더 혼난다"</div>
              </div>
            </div>
            <div style={{ marginTop: '18px', display: 'flex', flexWrap: 'wrap', gap: '20px' }}>
              <div style={{ flex: '1 1 360px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div className="note">주제 비중</div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '110px 1fr 40px',
                    gap: '10px',
                    alignItems: 'center',
                  }}
                >
                  <span>신체 체벌 경험</span>
                  <span className="bar">
                    <span style={{ width: '38%' }} />
                  </span>
                  <span className="note">38%</span>
                </div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '110px 1fr 40px',
                    gap: '10px',
                    alignItems: 'center',
                  }}
                >
                  <span>두려움 · 정서</span>
                  <span className="bar">
                    <span style={{ width: '27%' }} />
                  </span>
                  <span className="note">27%</span>
                </div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '110px 1fr 40px',
                    gap: '10px',
                    alignItems: 'center',
                  }}
                >
                  <span>보호자 관계</span>
                  <span className="bar">
                    <span style={{ width: '20%' }} />
                  </span>
                  <span className="note">20%</span>
                </div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '110px 1fr 40px',
                    gap: '10px',
                    alignItems: 'center',
                  }}
                >
                  <span>학교생활</span>
                  <span className="bar">
                    <span style={{ width: '10%' }} />
                  </span>
                  <span className="note">10%</span>
                </div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '110px 1fr 40px',
                    gap: '10px',
                    alignItems: 'center',
                  }}
                >
                  <span>식사 · 돌봄</span>
                  <span className="bar">
                    <span style={{ width: '5%' }} />
                  </span>
                  <span className="note">5%</span>
                </div>
              </div>
              <div style={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div className="box">
                  <b>덜 다룬 부분</b>
                  <div>식사 · 돌봄</div>
                  <div className="src">8회차 02:15 첫 언급</div>
                </div>
                <div className="box">
                  <b>체크인 연계</b>
                  <div>'두려움' ↔ 체크인 '조금 걱정돼' 3회 연속</div>
                </div>
              </div>
            </div>
          </section>
          <section className="card" aria-label="상담 회차" style={{ padding: '22px 24px' }}>
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                gap: '8px 12px',
                marginBottom: '14px',
              }}
            >
              <span className="secno">2</span>
              <h2 className="h2">상담 회차</h2>
            </div>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '12px',
              }}
            >
              {(v.sessions || []).map((s, sIndex) => (
                <Fragment key={sIndex}>
                  <A className="scard" to="/SessionDetail">
                    <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <b className="brn" style={{ fontSize: '18px' }}>
                        {s.no}
                      </b>
                      <span className={s.st} style={{ marginLeft: 'auto' }}>
                        {s.status}
                      </span>
                    </span>
                    <span style={{ fontSize: '14px' }}>{s.date}</span>
                    <span className="note">{s.kind}</span>
                    <span className="note">{s.sig}</span>
                  </A>
                </Fragment>
              ))}
            </div>
          </section>
          <section className="card" aria-label="회차별 세부 신호" style={{ padding: '22px 24px' }}>
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                gap: '8px 12px',
                marginBottom: '10px',
              }}
            >
              <span className="secno">3</span>
              <h2 className="h2">회차별 세부 신호</h2>
              <span className="src">채택 신호 · 근거 발화 수</span>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <div className="mx" style={{ minWidth: '640px' }}>
                <span className="rl note">세부 신호</span>
                {(v.cols || []).map((c, cIndex) => (
                  <Fragment key={cIndex}>
                    <A
                      to="/SessionDetail"
                      className="note"
                      style={{ textDecoration: 'none', color: '#5F6A73' }}
                    >
                      {c}
                    </A>
                  </Fragment>
                ))}
                {(v.mrows || []).map((r, rIndex) => (
                  <Fragment key={rIndex}>
                    <span className="rl">
                      <span
                        className="chip c-normal"
                        style={{ height: '20px', fontSize: '11px', marginRight: '6px' }}
                      >
                        {r.type}
                      </span>
                      {r.name}
                    </span>
                    {(r.cells || []).map((x, xIndex) => (
                      <Fragment key={xIndex}>
                        <span>
                          <span
                            className="dot"
                            title={x.tip}
                            style={{ background: x.bg, color: x.fg, boxShadow: x.ring }}
                          >
                            {x.v}
                          </span>
                        </span>
                      </Fragment>
                    ))}
                  </Fragment>
                ))}
              </div>
            </div>
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: '14px',
                marginTop: '10px',
                fontSize: '12px',
                color: '#6F7880',
              }}
            >
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                <span className="dot" style={{ width: '18px', height: '18px', background: '#EEE8DA' }} />
                1번
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                <span className="dot" style={{ width: '18px', height: '18px', background: '#6F7880' }} />
                2번 이상
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                <span
                  className="dot"
                  style={{
                    width: '18px',
                    height: '18px',
                    background: '#FFFFFF',
                    boxShadow: 'inset 0 0 0 1.5px #6F7880',
                  }}
                />
                보류 (화자 확인 중)
              </span>
            </div>
          </section>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
