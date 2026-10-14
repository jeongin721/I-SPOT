// 종결 검토 · 대상 아동 목록
// 원본: 다솔 님 디자인 counselor-web-design/Closure.dc.html (front_new 브랜치). 화면 값은 아직 예시(가상) 데이터다.
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useTheme } from '../theme';
import './Closure.css';

class Logic extends DCLogic {
  renderVals() {
    const s = this.state || {};
    return {
      name1: s.real ? '강시우' : '○시우',
      ini1: s.real ? '강' : '시',
      name2: s.real ? '조하린' : '○하린',
      ini2: s.real ? '조' : '하',
      real: !!s.real,
      tgBg: s.real ? '#2B2A26' : '#DAD5C9',
      tgX: s.real ? '16px' : '2px',
      toggleReal: () => this.setState({ real: !s.real }),
    };
  }
}

export default function Closure(props) {
  // 사이드바의 내 정보 · 로그아웃 · '관리자 메뉴'(관리자일 때만)에만 쓴다. 이 화면의 값은 아직 예시 데이터다.
  const session = useAuthSession();
  const theme = useTheme();
  const v = useDC(Logic, props);
  return (
    <div className="pg-Closure">
      <div
        className={theme.cls}
        style={{
          minHeight: '640px',
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
          <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>종결 검토</h1>
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 12px' }}>
            <input
              className="inp"
              type="search"
              aria-label="이름 또는 사례 ID 검색"
              placeholder="이름 · 사례 ID 검색"
              style={{ flex: '1 1 240px' }}
            />
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
                ></span>
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
                        {v.ini1}
                      </span>
                      <span>
                        {v.name1} <span className="note">7세</span>
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
                        {v.ini2}
                      </span>
                      <span>
                        {v.name2} <span className="note">14세</span>
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
