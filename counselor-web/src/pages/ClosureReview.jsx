// 종결 검토 › ① 전체 상담 내역 검토 (핵심 요약 + 근거 · 확인 후 보고서로)
// 원본: 다솔 님 디자인 counselor-web-design/ClosureReview.dc.html (front_new 브랜치). 화면 값은 아직 예시(가상) 데이터다.
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useTheme } from '../theme';
import './ClosureReview.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { ok: {}, txt: {}, edit: null, draft: '', tlAll: false };
  }
  renderVals() {
    const s = this.state;
    const G = [
      [
        '학대 관련 진술',
        [
          [
            'a1',
            '1~2회차에 개입 전 있었던 보호자(모)의 고성 · 위협적 언어를 진술함. 3회차 이후 새 학대 진술 없음.',
            '1회차 4/10 02:15 · 2회차 4/24 06:41 · 3~12회차 검수본 · 재신고 기록 없음',
          ],
          ['a2', '신체 학대 진술은 전 회차에서 없음.', '1~12회차 위험 신호 검토 결과 · 신체 채택 0건'],
        ],
      ],
      [
        '아동 정서 · 행동',
        [
          [
            'b1',
            '초기에 위축 · "숨고 싶다"는 표현이 잦았으나, 9회차 이후 학교 · 친구 이야기를 먼저 꺼냄.',
            '1회차 대상자 태도 · 8회차 03:20 · 9회차 01:05',
          ],
          ['b2', '11회차에 안전 계획(할머니 연락 · 112)을 자기 말로 설명함.', '11회차 9/18 · 03:12'],
        ],
      ],
      [
        '보호자(사례관리대상자) 변화',
        [
          [
            'c1',
            '부모교육 8/8회 이수. 6회차 보호자 상담에서 고성이 상처였다고 말함.',
            '서비스 기록 · 보호자 상담 6회차 9/4 · 상담일지',
          ],
          [
            'c2',
            '가정방문 3회 모두 협조적. 가족관계척도 평균 2.40 → 3.60.',
            '가정방문 6/19 · 8/14 · 9/25 · 가족관계척도 4/12 · 10/1',
          ],
        ],
      ],
      [
        '안전 자원 · 강점',
        [
          [
            'd1',
            '외조모가 주 2회 돌봄 (Key Person). 담임교사와도 연락 유지.',
            '5회차 6/5 01:40 · 보호자 상담 3회차 · 아이 연계 9월 QB-S-01',
          ],
        ],
      ],
      [
        '아이 연계',
        [
          [
            'e1',
            '5월 "무서워" 응답 3회 → 9~10월 "좋아 · 보통"만. 긴급 응답 0회.',
            '아이 연계 체크인 5/2 ~ 10/11 · QB-E-02',
          ],
          ['e2', '무서움 · 고성 관련 글 없음. 9/30 가족과 웃었다는 글.', '아이 연계 · 아이가 쓴 글 6/12 · 9/30'],
        ],
      ],
    ];
    const all = [];
    const groups = G.map(([title, items]) => ({
      title,
      items: items.map(([k, t, src]) => {
        all.push(k);
        const on = !!s.ok[k];
        const text = s.txt[k] !== undefined ? s.txt[k] : t;
        const ed = s.edit === k;
        return {
          text,
          src,
          on: on ? 'true' : 'false',
          mark: on ? '✓' : '',
          ckBg: on ? '#C2A36B' : '#FFFFFF',
          ckBd: on ? '#C2A36B' : '#CFC9BB',
          fixed: s.txt[k] !== undefined && s.txt[k] !== t,
          view: !ed,
          editing: ed,
          toggle: () => this.setState({ ok: { ...s.ok, [k]: !on } }),
          edit: () => this.setState({ edit: k, draft: text }),
        };
      }),
    }));
    const okCount = all.filter((k) => s.ok[k]).length;
    const allOk = okCount === all.length;
    const R = [
      ['1회차', '4/10', '초기면접 · 가정방문', '"엄마가 소리 지르면 숨고 싶어요" · 위축', '02:15 · 대상자 태도'],
      ['2회차', '4/24', '정기상담', '"너 버리고 간다고 했어요" (보호자는 부인)', '06:41'],
      ['3회차', '5/8', '정기상담', '감정 카드로 무서움 표현 · 안전 계획 처음 만듦', '04:10'],
      ['4회차', '5/22', '정기상담', '"요즘은 엄마가 덜 무서워요"', '02:50'],
      ['5회차', '6/5', '정기상담', '외조모 주 2회 돌봄 시작', '01:40'],
      ['6회차', '6/19', '가정방문', '보호자 동석 시 발화 줄어듦 · 집 환경 안정', '04:30 · 대상자 태도'],
      ['7회차', '7/3', '정기상담', '"집이 조용해졌어요"', '01:12'],
      ['8회차', '7/17', '정기상담', '학교 친구 이야기 · 목소리 밝아짐', '03:20'],
      ['9회차', '8/7', '정기상담', '새 진술 없음 · 먼저 학교 이야기 꺼냄', '01:05'],
      ['10회차', '8/28', '정기상담', '할머니 집 놀러 간 이야기', '02:30'],
      ['11회차', '9/18', '정기상담', '안전 계획을 자기 말로 설명', '03:12'],
      ['12회차', '10/7', '정기상담', '새 진술 없음 · 종결 이야기에 "괜찮아요"', '05:48'],
    ];
    const rows = (s.tlAll ? R : R.slice(0, 4).concat(R.slice(-2))).map(([no, date, kind, key, src]) => ({
      no,
      date,
      kind,
      key,
      src: no + ' ' + src,
    }));
    return {
      groups,
      okCount,
      total: all.length,
      allOk,
      notAllOk: !allOk,
      checkAllLabel: allOk ? '모두 해제' : '모두 확인',
      checkAll: () => this.setState({ ok: allOk ? {} : Object.fromEntries(all.map((k) => [k, true])) }),
      setDraft: (e) => this.setState({ draft: e.target.value }),
      saveEdit: () => this.setState({ txt: { ...s.txt, [s.edit]: s.draft }, edit: null }),
      cancelEdit: () => this.setState({ edit: null }),
      rows,
      tlLabel: s.tlAll ? '접기' : '12회차 모두 보기',
      toggleAll: () => this.setState({ tlAll: !s.tlAll }),
      doneTitle: allOk ? '전체 내역 확인 완료' : `확인 ${okCount} / ${all.length}`,
      doneSub: allOk
        ? '확인한 내용으로 종결보고서 초안이 채워져요'
        : '요약을 모두 확인하면 종결보고서를 작성할 수 있어요',
    };
  }
}

export default function ClosureReview(props) {
  // 사이드바의 내 정보 · 로그아웃 · '관리자 메뉴'(관리자일 때만)에만 쓴다. 이 화면의 값은 아직 예시 데이터다.
  const session = useAuthSession();
  const theme = useTheme();
  const v = useDC(Logic, props);
  return (
    <div className="pg-ClosureReview">
      <div
        className={theme.cls}
        style={{
          minHeight: '2300px',
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
            <A className="btn btn-sm btn-s" to="/Closure">
              ← 목록
            </A>
            <div style={{ flex: '1 1 320px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>강시우 · 전체 상담 내역 검토</h1>
                <span className="chip c-ai">AI 초안</span>
              </div>
              <div className="note">C-2026-0312 · 정서 · 7세 · 1~12회차 (4/10 ~ 10/7) · 아이 연계 (5/2 ~ 10/11)</div>
            </div>
            <A className="btn btn-s" to="/CaseHistory">
              상담 이력 원본
            </A>
          </header>
          <nav className="steps" aria-label="종결 검토 단계">
            <A className="stp on" to="/ClosureReview" aria-current="step">
              <span className="sn">1</span>
              <b style={{ fontWeight: '700' }}>전체 상담 내역 검토</b>
            </A>
            <A className="stp" to="/ClosureDetail">
              <span className="sn">2</span>
              <b style={{ fontWeight: '500' }}>종결보고서 작성</b>
            </A>
          </nav>

          <section
            aria-label="한눈에"
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '12px' }}
          >
            <div className="kpi">
              <span className="note">상담</span>
              <b>12회</b>
              <span className="src">아동 12 · 보호자 6 · 가정방문 3</span>
            </div>
            <div className="kpi">
              <span className="note">새 학대 진술</span>
              <b>없음</b>
              <span className="src">3~12회차 · 재신고 0건</span>
            </div>
            <div className="kpi">
              <span className="note">아이 연계 응답</span>
              <b>128 / 163일</b>
              <span className="src">긴급 응답 0회</span>
            </div>
            <div className="kpi">
              <span className="note">위험수준 척도 (위험요인)</span>
              <b>14 → 6</b>
              <span className="src">4/12 → 10/2 · 사정기록지</span>
            </div>
          </section>

          <section className="card" aria-label="핵심 요약" style={{ padding: '20px 24px' }}>
            <div
              style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px 12px', marginBottom: '4px' }}
            >
              <h2 className="h2">핵심 요약</h2>
              <span className="chip c-ai">AI 초안</span>
              <span style={{ marginLeft: 'auto', fontSize: '14px' }}>
                확인 <b>{v.okCount}</b> / {v.total}
              </span>
              <button type="button" className="btn btn-sm btn-s" onClick={v.checkAll}>
                {v.checkAllLabel}
              </button>
            </div>
            {(v.groups || []).map((g, gIndex) => (
              <Fragment key={gIndex}>
                <div style={{ marginTop: '16px' }}>
                  <b style={{ fontSize: '15px' }}>{g.title}</b>
                  {(g.items || []).map((it, itIndex) => (
                    <Fragment key={itIndex}>
                      <div className="pt">
                        <button
                          type="button"
                          className="ck"
                          role="checkbox"
                          aria-checked={it.on}
                          aria-label="확인"
                          onClick={it.toggle}
                          style={{ background: it.ckBg, borderColor: it.ckBd }}
                        >
                          {it.mark}
                        </button>
                        <div>
                          {it.view ? (
                            <>
                              <span style={{ fontSize: '14.5px' }}>{it.text}</span>
                              {it.fixed ? (
                                <>
                                  {' '}
                                  <span className="chip c-normal" style={{ height: '20px', fontSize: '11px' }}>
                                    상담사 수정
                                  </span>
                                </>
                              ) : null}
                            </>
                          ) : null}
                          {it.editing ? (
                            <>
                              <textarea
                                className="ta3"
                                aria-label="요약 고치기"
                                onChange={v.setDraft}
                                defaultValue={'{{ it.text }}'}
                              ></textarea>
                              <span style={{ display: 'flex', gap: '6px', marginTop: '6px' }}>
                                <button type="button" className="btn btn-sm btn-p" onClick={v.saveEdit}>
                                  저장
                                </button>
                                <button type="button" className="btn btn-sm btn-s" onClick={v.cancelEdit}>
                                  취소
                                </button>
                              </span>
                            </>
                          ) : null}
                          <span className="src">{it.src}</span>
                        </div>
                        {it.view ? (
                          <>
                            <button type="button" className="ed" onClick={it.edit}>
                              수정
                            </button>
                          </>
                        ) : null}
                      </div>
                    </Fragment>
                  ))}
                </div>
              </Fragment>
            ))}
          </section>

          <section
            className="card"
            aria-label="서로 다른 진술"
            style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '10px' }}
          >
            <h2 className="h2">
              서로 다른 진술{' '}
              <span className="note" style={{ fontWeight: '400' }}>
                합치지 않고 그대로
              </span>
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '10px' }}>
              <div className="qt">
                아동 "엄마가 '너 버리고 간다'고 했어요"<span className="src">2회차 4/24 · 06:41 (검수본)</span>
              </div>
              <div className="qt">
                보호자(모) "그런 말은 한 적 없어요"<span className="src">보호자 상담 2회차 5/15 · 상담일지</span>
              </div>
            </div>
          </section>

          <section className="card" aria-label="회차별 흐름" style={{ overflowX: 'auto' }}>
            <div className="hd">
              <h2 className="h2">회차별 흐름</h2>
              <button type="button" className="btn btn-sm btn-s" style={{ marginLeft: 'auto' }} onClick={v.toggleAll}>
                {v.tlLabel}
              </button>
            </div>
            <table className="tbl tl" style={{ minWidth: '680px' }}>
              <thead>
                <tr>
                  <th>회차</th>
                  <th>날짜</th>
                  <th>유형</th>
                  <th>핵심</th>
                  <th>근거</th>
                </tr>
              </thead>
              <tbody>
                {(v.rows || []).map((r, rIndex) => (
                  <Fragment key={rIndex}>
                    <tr>
                      <td>
                        <b>{r.no}</b>
                      </td>
                      <td className="note">{r.date}</td>
                      <td className="note">{r.kind}</td>
                      <td>{r.key}</td>
                      <td>
                        <span className="src" style={{ margin: '0' }}>
                          {r.src}
                        </span>
                      </td>
                    </tr>
                  </Fragment>
                ))}
              </tbody>
            </table>
          </section>

          <section
            className="card"
            aria-label="아이 연계"
            style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '12px' }}
          >
            <h2 className="h2">아이 연계</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '10px' }}>
              <div className="qt">
                "오늘 엄마랑 그림 그렸어"<span className="src">아이가 쓴 글 · 6/12 21:40</span>
              </div>
              <div className="qt">
                "할머니랑 떡볶이 먹었다. 엄마도 같이 웃었어"<span className="src">아이가 쓴 글 · 9/30 19:05</span>
              </div>
            </div>
            <table className="tbl tl">
              <thead>
                <tr>
                  <th>질문</th>
                  <th>5월</th>
                  <th>7월</th>
                  <th>9~10월</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>요즘 기분은 어때?</td>
                  <td>무서워 · 3회</td>
                  <td>보통</td>
                  <td>
                    <b>좋아 · 보통</b>
                  </td>
                </tr>
                <tr>
                  <td>집에서 큰 소리가 났어?</td>
                  <td>가끔</td>
                  <td>거의 없어</td>
                  <td>
                    <b>없어</b>
                  </td>
                </tr>
                <tr>
                  <td>힘들 때 누구한테 말해?</td>
                  <td>없어</td>
                  <td>할머니</td>
                  <td>
                    <b>할머니 · 선생님</b>
                  </td>
                </tr>
              </tbody>
            </table>
            <span className="src" style={{ margin: '0' }}>
              체크인 QB-E-02 · QB-H-04 · QB-S-01 · 월별 가장 많은 답
            </span>
          </section>

          <section
            className="card"
            style={{ padding: '18px 22px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px' }}
          >
            <div style={{ flex: '1 1 300px' }}>
              <b>{v.doneTitle}</b>
              <span className="note" style={{ display: 'block' }}>
                {v.doneSub}
              </span>
            </div>
            {v.allOk ? (
              <>
                <A className="btn btn-p" to="/ClosureDetail">
                  종결보고서 작성 →
                </A>
              </>
            ) : null}
            {v.notAllOk ? (
              <>
                <span className="btn" style={{ background: '#F2EFE8', color: '#98948B', cursor: 'default' }}>
                  종결보고서 작성 →
                </span>
              </>
            ) : null}
          </section>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
