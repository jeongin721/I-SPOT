// 관리자 화면 왼쪽 메뉴(10/21 디자인 Admin*.dc.html 의 aside.side). 디자인에서 7장마다 똑같이 반복되던 마크업을 한곳에 모았다.
// - active: 굵게 표시할 메뉴의 화면 이름(예: 'AdminAccounts'). 상담사 상세(AdminStaffDetail)는 'AdminAccounts'.
// - session: useAuthSession() 결과. 아래 내 정보 · 로그아웃(src/data/screens/common.ts 의 sidebarValues)에 쓴다.
//
// 메뉴는 디자인 순서 그대로다: 홈 · 아이 연계 앱 관리 · 상담사 계정 관리 · 열람 기록 · 접속 기록 · 보안 이벤트 · 통계 · 보고.
//  - 아이 연계 앱 관리 · 열람 기록은 서버가 없어(팀 결정 A2 · B2 대기) 상담원 메뉴의 '문서함' 처럼 링크 없이 '준비 중' 으로 둔다.
//  - 디자인의 메뉴 옆 숫자(2 · 3)는 서버에 없는 예시 값이라 넣지 않는다.
//  - 디자인에는 없지만 앱에 있던 관리자 기능(업무 처리 현황 · 전체 사례 현황 · 상담원 화면으로)은 아래 묶음으로 남긴다(팀 질문 D5 의 추천).
// 900px 이하의 '메뉴' 단추(#mnav 체크박스)는 상담원 메뉴와 같은 CSS 로 펼친다(common.css 반응형 블록).
//
// AdminBlocked: 관리자가 아니거나 로그인을 확인하지 못했을 때 모든 관리자 화면이 메뉴 대신 보이는 안내(서버는 부르지 않는다).
import A from './A';
import Notice from './Notice';
import { useTheme } from '../theme';
import { NOT_READY, sidebarValues } from '../data/screens/common';
import { adminBlockedNotice } from '../data/screens/admin';

const off = { opacity: 0.5, cursor: 'not-allowed' };

// [화면 이름, 메뉴 글자]. 화면 이름이 null 이면 아직 화면이 없는 '준비 중' 항목이다.
const MENU = [
  ['AdminHome', '홈'],
  [null, '아이 연계 앱 관리'],
  ['AdminAccounts', '상담사 계정 관리'],
  [null, '열람 기록'],
  ['AdminSecurity', '접속 기록 · 보안 이벤트'],
  ['AdminStats', '통계 · 보고'],
];

// 앱에 있던 관리자 기능. 업무 처리 현황은 관리자 화면, 나머지는 상담원 화면으로 간다.
const MENU_APP = [
  ['AdminTasks', '업무 처리 현황'],
  ['CaseList', '전체 사례 현황'],
  ['Main', '상담원 화면으로'],
];

export default function AdminSidebar({ active, session }) {
  const me = sidebarValues(session);
  const menuLink = ([name, label]) =>
    name ? (
      <A key={label} className={active === name ? 'on' : undefined} to={`/${name}`}>
        {label}
      </A>
    ) : (
      <a key={label} aria-disabled="true" title={NOT_READY} style={off}>
        {label}
      </a>
    );
  return (
    <aside className="side" aria-label="주 메뉴">
      <A className="logo" to="/AdminHome">
        <span className="mk">IS</span>
        <b style={{ fontSize: '17px' }}>I-SPOT</b>
        <span className="chip c-normal" style={{ marginLeft: '2px' }}>
          관리자
        </span>
      </A>
      <input type="checkbox" id="mnav" className="mnav-tg" aria-label="메뉴 열기" />
      <label htmlFor="mnav" className="mnav-btn">
        <i aria-hidden="true"></i>메뉴
      </label>
      <nav className="nav" aria-label="관리자 메뉴">
        {MENU.map(menuLink)}
        <div className="grp">업무 · 상담원 화면</div>
        {MENU_APP.map(menuLink)}
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

export function AdminBlocked({ session }) {
  const theme = useTheme();
  return (
    <div className="pg-Admin">
      <div
        className={theme.cls}
        style={{
          minHeight: '100vh',
          background: '#F2F2F0',
          color: '#2B2A26',
          fontFamily: "'IBM Plex Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          padding: '48px 36px',
        }}
      >
        <Notice value={adminBlockedNotice(session)} />
      </div>
    </div>
  );
}
