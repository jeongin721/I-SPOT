// 관리자 홈(기관 현황) — 디자인 AdminHome.dc.html(v2).
//  - 진행 중 사례 = senior-overview 가운데 종결 · 서비스 종료가 아닌 고령자 사례, 담당 상담사 수.
//  - 활성 상담사 / 전체 = GET /auth/users(관리자 전용, 상담사로 열면 403 → 안내만). 재배정 필요 = 담당자가 비활성인 진행 중 사례.
//  - 최근 접속 활동 = GET /auth/audit-logs?action=LOGIN 최근 8건. 접속 위치(기관 내부망 · 외부)는 서버에 기준이 없어 '—'.
//  - 상담사별 업무량: 담당 사례(진행 중) · 이번 주 상담(일정 중 상담) · 기록 확인 대기(원문 검수 · 분석 결과 검토 업무, 고령자 사례만).
//    위기도 · 일지 미작성은 고령자에 없는 값이라 '—'.
//  - 긴급 알림 현황(안부 연계 앱)은 서버에 없어 '준비 중' 한 줄. 수를 세기만 하고 판정하지 않는다.
import { useDC } from '../dc';
import DesignLogic from '../design/AdminHome.logic';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { loadAdminHome, adminHomeVals } from './AdminHome.parts';
import View from './AdminHome.view';

class Logic extends DesignLogic {
  renderValsBase() {
    return adminHomeVals(super.renderValsBase(), this.props.shell, this.props.data);
  }
}

export default function AdminHome(props) {
  const shell = useShell();
  const data = useAsync(() => (shell.ready ? loadAdminHome() : null), [shell.ready]);
  const v = useDC(Logic, { ...props, shell, data });
  return <View v={v} />;
}
