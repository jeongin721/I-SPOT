// 상담원 화면 왼쪽 메뉴(디자인의 aside.side "주 메뉴"). 디자인에서 화면마다 똑같이 반복되던 마크업을 한곳에 모았다.
// - active: 굵게 표시할 메뉴의 화면 이름(예: 'CaseList'). 사례 상세 · 회차 화면은 'CaseList'.
// - session: useAuthSession() 결과. 아래 내 정보 · 로그아웃(src/data/screens/common.ts 의 sidebarValues)과
//   '관리자 메뉴' 링크(관리자 계정일 때만)에 쓴다.
// 디자인의 메뉴 옆 숫자(아이 연계 4 · 종결 검토 2)는 서버에 없는 예시 값이라 넣지 않는다.
import A from './A';
import { sidebarValues } from '../data/screens/common';

const MENU = [
  ['Main', '홈'],
  ['CaseList', '사례 관리'],
  ['Schedule', '일정'],
  ['ChildLink', '아이 연계'],
  ['Closure', '종결 검토'],
  ['Stats', '통계'],
  ['Settings', '설정'],
];

export default function Sidebar({ active, session }) {
  const me = sidebarValues(session);
  return (
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
        {MENU.map(([name, label]) => (
          <A key={name} className={active === name ? 'on' : undefined} to={`/${name}`}>
            {label}
          </A>
        ))}
        {session.isAdmin ? <A to="/Admin">관리자 메뉴</A> : null}
      </nav>
      <div className="me">
        <span className="av">{me.meInitial}</span>
        <b style={{ fontWeight: '500' }}>{me.meName}</b>
        <A to="/Login" className="note" style={{ marginLeft: 'auto' }} onClick={me.logout}>
          로그아웃
        </A>
      </div>
    </aside>
  );
}
