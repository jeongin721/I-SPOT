// 탭 5 · 문서함 (기관 서식 6종 + 파일)
// 원본: I-SPOT 디자인 캔버스 보드 CaseDocs.dc.html (자동 변환 후 다듬어 쓰세요)
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { f: 'all' };
  }
  renderVals() {
    const s = this.state;
    const all = [
      [
        '방문상담_1002.m4a',
        '녹취',
        '8회차',
        '10/07 업로드',
        '검수 대기',
        'chip c-check',
        '/SttReview',
        'STT 검수',
        'rec',
      ],
      ['8회차 STT 검수본', '녹취', '8회차', '10/07', '검수 중', 'chip c-check', '/SttReview', '열기', 'rec'],
      ['7회차 상담일지', '상담 일지', '7회차', '09/18', '확정', 'chip c-ok', '/CaseHistory', '열기', 'note'],
      ['6회차 상담일지', '상담 일지', '6회차', '09/04', '확정', 'chip c-ok', '/CaseHistory', '열기', 'note'],
      [
        '9회차 상담 전 브리핑',
        '브리핑',
        '9회차',
        '10/08',
        '준비됨',
        'chip c-sky',
        '/PreBriefing',
        '열기',
        'brief',
      ],
      [
        '심리치료 소견서_9월.pdf',
        '외부 문서',
        '—',
        '09/30',
        '보관',
        'chip c-normal',
        '/CaseDocs',
        '열기',
        'ext',
      ],
      [
        '초기 조사 보고서.hwpx',
        '외부 문서',
        '—',
        '07/29',
        '보관',
        'chip c-normal',
        '/CaseDocs',
        '열기',
        'ext',
      ],
      [
        '7회차 녹취_0918.m4a',
        '녹취',
        '7회차',
        '09/18',
        '검수 완료',
        'chip c-ok',
        '/CaseHistory',
        '열기',
        'rec',
      ],
    ];
    const rows = all
      .filter((d) => s.f === 'all' || d[8] === s.f)
      .map((d) => ({
        name: d[0],
        kind: d[1],
        ses: d[2],
        date: d[3],
        st: d[4],
        stCls: d[5],
        href: d[6],
        go: d[7],
      }));
    const filters = [
      ['all', '전체'],
      ['rec', '녹취'],
      ['note', '상담 일지'],
      ['brief', '브리핑'],
      ['ext', '외부 문서'],
    ].map(([k, l]) => ({ label: l, cls: s.f === k ? 'on' : '', pick: () => this.setState({ f: k }) }));
    const forms = [
      [
        '초기면접지 (아동용)',
        '서식 4',
        '사례 등록 · 최초면접',
        '2026-07-29',
        '확정',
        'chip c-ok',
        '/CaseRegister',
        '열기',
      ],
      [
        '사정기록지 · 안전영역',
        '서식 6',
        '초기 사정 · 재사정',
        '2026-09-18',
        '재사정 필요',
        'chip c-check',
        '/CaseForm',
        '작성',
      ],
      [
        '사례관리 점검표',
        '서식 27',
        '3개월마다',
        '2026-09-14 (2차)',
        '3차 AI 초안',
        'chip c-sky',
        '/CaseForm',
        '작성',
      ],
      [
        '위험수준별 개입 사정 척도',
        '참고자료 3',
        '사정 · 재사정',
        '2026-09-18',
        'AI 제안 12개',
        'chip c-sky',
        '/CaseForm',
        '작성',
      ],
      [
        '축약형 가족관계 척도',
        '참고자료 1',
        '초기 · 종결',
        '2026-08-02',
        '응답 받기 전',
        'chip c-normal',
        '/CaseForm',
        '작성',
      ],
      [
        '사례관리 종결보고서',
        '서식 29',
        '종결 검토 등록 후',
        '—',
        '등록 전',
        'chip c-normal',
        '/ClosureDetail',
        '예시 보기',
      ],
    ].map((d) => ({
      name: d[0],
      no: d[1],
      when: d[2],
      date: d[3],
      st: d[4],
      stCls: d[5],
      href: d[6],
      go: d[7],
    }));
    return { rows, filters, forms };
  }
}

export default function CaseDocs(props) {
  const v = useDC(Logic, props);
  return (
    <div className="pg-CaseDocs">
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
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px' }}>
            <div role="group" aria-label="문서 종류" className="seg">
              {(v.filters || []).map((f, fIndex) => (
                <Fragment key={fIndex}>
                  <button type="button" className={f.cls} onClick={f.pick}>
                    {f.label}
                  </button>
                </Fragment>
              ))}
            </div>
            <A className="btn btn-p" to="/UploadModal" style={{ marginLeft: 'auto' }}>
              ↑ 자료 올리기
            </A>
          </section>
          <section className="card" aria-label="기관 서식" style={{ overflowX: 'auto' }}>
            <div className="hd">
              <h2 className="h2">기관 서식</h2>
            </div>
            <table className="tbl" style={{ minWidth: '680px' }}>
              <thead>
                <tr>
                  <th>서식</th>
                  <th>작성 시점</th>
                  <th>최근 작성</th>
                  <th>상태</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(v.forms || []).map((r, rIndex) => (
                  <Fragment key={rIndex}>
                    <tr>
                      <td>
                        <b style={{ fontWeight: '500' }}>{r.name}</b>
                        <span className="note" style={{ display: 'block' }}>
                          {r.no}
                        </span>
                      </td>
                      <td className="note">{r.when}</td>
                      <td className="note">{r.date}</td>
                      <td>
                        <span className={r.stCls}>{r.st}</span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <A to={r.href}>{r.go}</A>
                      </td>
                    </tr>
                  </Fragment>
                ))}
              </tbody>
            </table>
          </section>
          <section className="card" aria-label="파일" style={{ overflowX: 'auto' }}>
            <div className="hd">
              <h2 className="h2">녹취 · 일지 · 외부 문서</h2>
            </div>
            <table className="tbl" style={{ minWidth: '680px' }}>
              <thead>
                <tr>
                  <th>파일</th>
                  <th>종류</th>
                  <th>회차</th>
                  <th>날짜</th>
                  <th>상태</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(v.rows || []).map((r, rIndex) => (
                  <Fragment key={rIndex}>
                    <tr>
                      <td>
                        <b style={{ fontWeight: '500' }}>{r.name}</b>
                      </td>
                      <td className="note">{r.kind}</td>
                      <td>{r.ses}</td>
                      <td className="note">{r.date}</td>
                      <td>
                        <span className={r.stCls}>{r.st}</span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <A to={r.href}>{r.go}</A>
                      </td>
                    </tr>
                  </Fragment>
                ))}
              </tbody>
            </table>
          </section>
        </main>
      </div>
    </div>
  );
}
