// 상담사 앱(폰) · 홈 — 디자인 AppHome.dc.html.
//  - 인사: 로그인한 상담사 이름(GET /auth/me). 아래 줄은 오늘 날짜 · 오늘 상담 수.
//  - 내 사례 현황: 담당 사례 = 내 진행 중 고령자 사례 수, 이번 주 상담 · 오늘 상담 = 이번 주(월~일) · 오늘 일정 중 상담(GET /schedule/events).
//  - 시니어 상담 공지사항: 공지를 둘 서버 자리가 없어 '준비 중' 한 줄만(디자인의 예시 공지 3개는 넣지 않는다).
//  - 알림(종): App.parts 의 공통 알림(업로드 실패 · 오늘 남은 상담).
import { useDC } from '../dc';
import DesignLogic from '../design/AppHome.logic';
import { useAppSchedule } from '@cw/data/useAppSchedule';
import { DASH } from '../data/format';
import { useAppData, withApp, dayKey, addDays, mondayOf } from './App.parts';
import View from './AppHome.view';

const W = ['일', '월', '화', '수', '목', '금', '토'];

class Logic extends withApp(DesignLogic) {
  renderVals() {
    const v = super.renderVals();
    const { app, week } = this.props;
    const now = new Date();
    const today = dayKey(now);
    const consults = week.items.filter((e) => e.kind === 'CONSULT');
    const todayN = consults.filter((e) => e.date === today).length;
    const num = (n, loading) => (loading ? DASH : String(n));
    const me = app.me;
    return {
      ...v,
      hello: me && me.name ? (me.name.endsWith('상담사') ? `${me.name}님` : `${me.name} 상담사님`) : '상담사님',
      today: `${now.getMonth() + 1}월 ${now.getDate()}일 ${W[now.getDay()]}요일 · 오늘 상담 ${week.loading ? DASH : todayN}건`,
      statCases: num(app.elders.length, app.eldersLoading),
      statWeek: num(consults.length, week.loading),
      statToday: num(todayN, week.loading),
      unreadN: '준비 중',
      notices: [{ title: '공지사항은 준비 중이에요', meta: '', imp: false, cls: 'li', open: () => {} }],
      shOpen: false,
      loadErr: app.eldersErr || week.error || '',
    };
  }
}

export default function AppHome(props) {
  const app = useAppData();
  const mon = mondayOf(new Date());
  const week = useAppSchedule(!!app.userId, dayKey(mon), dayKey(addDays(mon, 6)));
  const v = useDC(Logic, { ...props, app, week });
  return <View v={v} />;
}
