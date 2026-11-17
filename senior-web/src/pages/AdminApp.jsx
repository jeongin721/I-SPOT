// 관리자 · 안부 연계 앱 관리 — 디자인 AdminApp.dc.html(v2). 관리자 전용 화면.
//  - 고령자 안부 앱은 아직 없다(아동 콩콩 API 는 아동 사례만이라 쓰지 않는다). 화면 틀만 두고 앱 연결 · 가족 연결 ·
//    무응답 숫자와 두 표는 '—' · 준비 중으로 비운다(디자인의 예시 어르신 · 숫자는 남기지 않는다).
//  - '전체 어르신' 만 서버 값: senior-overview 의 진행 중(ACTIVE) 고령자 대상자 수.
//  - 관리자가 아니면 서버를 부르지 않고 안내만 보인다.
import { useDC } from '../dc';
import DesignLogic from '../design/AdminApp.logic';
import { senior } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { DASH } from '../data/format';
import { errText } from './Step3Summary.basis';
import { isAdmin, DENIED, sideVals } from './AdminSecurity';
import View from './AdminApp.view';

const NOTE = '고령자 안부 앱은 준비 중이에요. 앱 연결 · 가족 연결 · 무응답 기록이 생기면 여기에 보여요.';

class Logic extends DesignLogic {
  renderValsBase() {
    const s = this.state;
    const { shell, data } = this.props;
    const segOf = (key, cur, opts) => opts.map(([v, l]) => ({ label: l, cls: cur === v ? 'on' : '', pressed: cur === v ? 'true' : 'false', pick: () => this.setState({ [key]: v }) }));
    const base = {
      ...sideVals(shell),
      totalElders: DASH, totalNote: `진행 중 사례 기준 · 가족 연결 ${DASH}`,
      onCnt: DASH, onNote: '준비 중', offCnt: DASH, offNote: '준비 중',
      stackAria: '안부 앱 연결 현황 준비 중', wOn: '0%', wWait: '0%', wOff: '0%',
      lgOn: `연결됨 ${DASH}`, lgWait: `초대 대기 ${DASH}`, lgOff: `미연결 ${DASH}`,
      conn: [], silent: [], silentCnt: DASH, silentOpen: DASH,
      cFilters: segOf('cf', s.cf, [['all', '전체'], ['on', '연결됨'], ['wait', '초대 대기'], ['off', '미연결']]),
      sFilters: segOf('sf', s.sf, [['all', '전체'], ['open', '미처리']]),
      msg: NOTE,
    };
    if (shell.ready && !isAdmin(shell)) return { ...base, msg: DENIED };
    if (data.error) return { ...base, msg: `${errText(data.error, '대상자 수를 불러오지 못했어요.')} ${NOTE}` };
    const ov = data.data;
    if (!ov) return base;
    return { ...base, totalElders: ov.rows.filter((r) => r.case_status === 'ACTIVE').length };
  }
}

export default function AdminApp(props) {
  const shell = useShell();
  const admin = isAdmin(shell);
  const data = useAsync(async () => {
    if (!shell.ready || !admin) return null;
    return senior.overview();
  }, [shell.ready, admin]);
  const v = useDC(Logic, { ...props, shell, data });
  return <View v={v} />;
}
