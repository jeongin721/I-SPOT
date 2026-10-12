// 통합 사례 관리 (사례 ID · 이름 · 신고접수일 · 위험도)
// 원본: I-SPOT 디자인 캔버스 보드 CaseList.dc.html (자동 변환 후 다듬어 쓰세요)
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import './CaseList.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { f: 'all', real: false };
  }
  renderVals() {
    const s = this.state;
    const cls = { 상: 'chip c-hi', 중: 'chip c-mid', 하: 'chip c-lo' };
    const data = [
      ['C-2026-0277', '장', '민준', '9세', '2026-06-02', '상'],
      ['C-2026-0351', '이', '서윤', '13세', '2026-07-28', '상'],
      ['C-2026-0412', '김', '도현', '8세', '2026-08-19', '상'],
      ['C-2026-0389', '박', '지호', '11세', '2026-09-03', '중'],
      ['C-2026-0338', '정', '예린', '9세', '2026-08-05', '중'],
      ['C-2026-0374', '최', '서준', '6세', '2026-09-25', '중'],
      ['C-2026-0298', '윤', '하은', '10세', '2026-06-20', '중'],
      ['C-2026-0229', '신', '유나', '8세', '2026-05-14', '하'],
      ['C-2026-0312', '강', '시우', '7세', '2026-04-08', '하'],
      ['C-2026-0251', '조', '하린', '14세', '2026-05-30', '하'],
    ];
    const rows = data
      .filter((d) => s.f === 'all' || d[5] === s.f)
      .map((d) => ({
        id: d[0],
        ini: s.real ? d[1] : d[2].slice(0, 1),
        name: s.real ? d[1] + d[2] : '○' + d[2],
        age: d[3],
        date: d[4],
        risk: d[5],
        cls: cls[d[5]],
      }));
    const filters = [
      ['all', '전체 10'],
      ['상', '상 3'],
      ['중', '중 4'],
      ['하', '하 3'],
    ].map(([k, label]) => ({ label, cls: s.f === k ? 'on' : '', pick: () => this.setState({ f: k }) }));
    return {
      rows,
      filters,
      real: s.real,
      tgBg: s.real ? '#A8C6E7' : '#DCD5C3',
      tgX: s.real ? '16px' : '2px',
      toggleReal: () => this.setState({ real: !s.real }),
    };
  }
}

export default function CaseList(props) {
  const v = useDC(Logic, props);
  return (
    <div className="pg-CaseList">
      <div
        style={{
          minHeight: '960px',
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
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 260px' }}>
              <div className="sub">담당 사례 10건</div>
              <h1 style={{ margin: '2px 0 0', fontSize: '28px', fontWeight: '700' }}>통합 사례 관리</h1>
            </div>
          </header>
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 12px' }}>
            <input
              className="inp"
              type="search"
              aria-label="이름 또는 사례 ID 검색"
              placeholder="이름 · 사례 ID 검색"
              style={{ flex: '1 1 240px' }}
            />
            <div role="group" aria-label="위험도" className="seg">
              {(v.filters || []).map((f, fIndex) => (
                <Fragment key={fIndex}>
                  <button type="button" className={f.cls} onClick={f.pick}>
                    {f.label}
                  </button>
                </Fragment>
              ))}
            </div>
            <button type="button" className="tg" aria-pressed={v.real} onClick={v.toggleReal}>
              <span
                style={{
                  width: '34px',
                  height: '20px',
                  borderRadius: '10px',
                  background: v.tgBg,
                  position: 'relative',
                  display: 'inline-block',
                }}
              >
                <span
                  style={{
                    position: 'absolute',
                    top: '2px',
                    left: v.tgX,
                    width: '16px',
                    height: '16px',
                    borderRadius: '50%',
                    background: '#FFFFFF',
                    boxShadow: '0 1px 2px rgba(0,0,0,.2)',
                  }}
                />
              </span>
              실명 보기
            </button>
          </section>
          {v.real ? (
            <>
              <p className="note" style={{ margin: '-8px 0 0' }}>
                실명 표시 중 · 열람 기록 남음
              </p>
            </>
          ) : null}
          <section className="card" style={{ overflowX: 'auto' }}>
            <table className="tbl" style={{ minWidth: '640px' }}>
              <thead>
                <tr>
                  <th scope="col">사례 ID</th>
                  <th scope="col">이름</th>
                  <th scope="col">신고접수일</th>
                  <th scope="col">위험도</th>
                  <th scope="col">
                    <span style={{ position: 'absolute', left: '-9999px' }}>상세</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {(v.rows || []).map((r, rIndex) => (
                  <Fragment key={rIndex}>
                    <tr>
                      <td className="note">{r.id}</td>
                      <td>
                        <A className="nm" to="/CaseDetail">
                          <span className="av" style={{ width: '34px', height: '34px', fontSize: '13px' }}>
                            {r.ini}
                          </span>
                          <span>
                            {r.name} <span className="note">{r.age}</span>
                          </span>
                        </A>
                      </td>
                      <td>{r.date}</td>
                      <td>
                        <span className={r.cls} style={{ minWidth: '44px', justifyContent: 'center' }}>
                          {r.risk}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <A to="/CaseDetail">상세</A>
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
