// 종결 검토 · 대상 아동 목록
// 원본: I-SPOT 디자인 캔버스 보드 Closure.dc.html (자동 변환 후 다듬어 쓰세요)
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import './Closure.css';

class Logic extends DCLogic {
  renderVals() {
    return {};
  }
}

export default function Closure(props) {
  const v = useDC(Logic, props);
  return (
    <div className="pg-Closure">
      <div
        style={{
          minHeight: '640px',
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
            <A to="/CaseList">사례 관리</A>
            <A to="/Schedule">일정</A>
            <A to="/ChildLink">
              아이 연계<span className="cnt">4</span>
            </A>
            <A className="on" to="/Closure">
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
          <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>종결 검토</h1>
          <section className="card" style={{ overflowX: 'auto' }}>
            <table className="tbl" style={{ minWidth: '600px' }}>
              <thead>
                <tr>
                  <th scope="col">아동 이름</th>
                  <th scope="col">상담 회차</th>
                  <th scope="col">등록일</th>
                  <th scope="col">진행 단계</th>
                  <th scope="col">내역 검토</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>
                    <A className="nm" to="/ClosureReview">
                      <span className="av" style={{ width: '34px', height: '34px', fontSize: '13px' }}>
                        시
                      </span>
                      <span>
                        강시우 <span className="note">7세</span>
                        <span className="note" style={{ display: 'block', fontWeight: '400' }}>
                          C-2026-0312 · 정서
                        </span>
                      </span>
                    </A>
                  </td>
                  <td>12회차</td>
                  <td>10/1</td>
                  <td>
                    <span className="chip c-ok">① 내역 검토</span>
                  </td>
                  <td>
                    <b>0 / 9</b>
                  </td>
                </tr>
                <tr>
                  <td>
                    <span className="nm">
                      <span className="av" style={{ width: '34px', height: '34px', fontSize: '13px' }}>
                        하
                      </span>
                      <span>
                        조하린 <span className="note">14세</span>
                        <span className="note" style={{ display: 'block', fontWeight: '400' }}>
                          C-2026-0251 · 방임
                        </span>
                      </span>
                    </span>
                  </td>
                  <td>9회차</td>
                  <td>오늘</td>
                  <td>
                    <span className="chip c-sky">요약 만드는 중</span>
                  </td>
                  <td className="note">—</td>
                </tr>
              </tbody>
            </table>
          </section>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
