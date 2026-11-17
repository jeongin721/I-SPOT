// 상담사 앱(폰) · 이전 상담 — 디자인 AppHistory.dc.html. 웹 사례 상세 › 상담 이력(CaseHistory)과 같은 값.
//  - 대상자: 주소의 ?case=(앱 대상자 목록의 '이전 상담').
//  - 요약 칸: 총 회차 · 첫 ~ 마지막 상담일, 최근 세 회차(제목 · 요약 첫 말씀), 주제 비중 = 생활 · 정서 영역별 근거 발화 수 비율(care-domains). AI 판정 아님.
//  - 회차별: 회차 목록(상태 · 상담 방식) + senior-history(요약 · 영역 변화). 상담 일지는 회차 메모, 주요 발화는 영역 기록의 어르신 말씀,
//    칩은 달라짐 · 처음 기록된 영역. 고령자에는 학대 신호 · 위기도가 없다.
import { useDC } from '../dc';
import DesignLogic from '../design/AppHistory.logic';
import { cases } from '@cw/api/endpoints';
import { senior, CHANGE_LABELS } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useIds } from '../data/nav';
import { DASH, md, ymd } from '../data/format';
import { useAppData, withApp, nameOf, sessionKind } from './App.parts';
import View from './AppHistory.view';

const soft = (p) => p.catch(() => null);
// 처리 단계만 적는다(판정 말 없음).
const STATUS = {
  CREATED: '녹음 전', AUDIO_UPLOADED: '변환 대기', STT_PROCESSING: '변환 중', STT_REVIEW_REQUIRED: '검수 대기', STT_CONFIRMED: '분석 대기',
  AI_PROCESSING: '분석 중', AI_REVIEW_REQUIRED: '요약 검토 대기', APPROVED: '확정', STT_FAILED: '변환 실패', AI_FAILED: '분석 실패',
};
const firstPoint = (summary) => ((summary && summary.key_points) || []).find((x) => x && !x.startsWith('이번 측정')) || '';

class Logic extends withApp(DesignLogic) {
  renderVals() {
    const v = super.renderVals();
    const { data, loadErr } = this.props;
    const d = data || {};
    const c = d.c;
    const list = d.sessions || []; // 회차 번호 큰 것부터
    const visits = Object.fromEntries(((d.history && d.history.entries) || []).filter((e) => e.kind === 'VISIT' && e.session_id).map((e) => [e.session_id, e]));
    const asc = [...list].reverse();
    const at = (s) => s.consulted_at || s.created_at;
    const first = asc[0];
    const last = asc[asc.length - 1];

    const flow = asc.slice(-3).map((s, i, arr) => {
      const quote = firstPoint(visits[s.id] && visits[s.id].summary);
      return { k: `${s.session_number}회차`, t: s.title || `${s.session_number}회차`, d: `${md(at(s))}${quote ? ` · "${quote}"` : ''}${i === arr.length - 1 ? ' · 최근' : ''}` };
    });
    const tl = (d.timeline && d.timeline.domains) || [];
    const counts = tl.map((g) => ({ k: g.label, n: g.entries.reduce((a, e) => a + (e.change === 'NOT_MENTIONED' ? 0 : (e.segment_ids || []).length), 0) }));
    const sum = counts.reduce((a, x) => a + x.n, 0);
    const bars = sum ? [...counts].sort((a, b) => b.n - a.n).filter((x) => x.n > 0).map((x) => ({ k: x.k, v: String(Math.round((x.n / sum) * 100)) })) : [];

    const ses = list.map((s) => {
      const e = visits[s.id];
      const sm = e && e.summary;
      const doms = ((e && e.care_domains) || []).filter((x) => x.change !== 'NOT_MENTIONED');
      const label = (x) => (tl.find((g) => g.domain === x.domain) || {}).label || x.domain;
      const sigs = doms.filter((x) => x.change === 'CHANGED' || x.change === 'NEW').map((x) => `${label(x)} · ${CHANGE_LABELS[x.change]}`);
      const lines = doms.filter((x) => x.text).map((x) => ({ t: label(x), sp: CHANGE_LABELS[x.change], s: x.text }));
      const approved = s.status === 'APPROVED';
      return {
        no: `${s.session_number}회차`,
        date: ymd(at(s)),
        kind: sessionKind(s.consultation_type),
        st: STATUS[s.status] || DASH,
        stCls: approved ? 'chip' : 'chip gold',
        sumLb: sm && sm.status === 'APPROVED' ? '상담 요약' : 'AI 요약 (웹에서 확정 전)',
        sum: (sm && sm.overview) || DASH,
        hasDiary: !!s.memo,
        diary: s.memo || '',
        hasLines: lines.length > 0,
        lines,
        hasSig: sigs.length > 0,
        sigs,
      };
    });
    return {
      ...v,
      sub: c ? `${nameOf(c)} · ${c.case_number || DASH}` : DASH,
      range: list.length ? `총 ${list.length}회 · ${md(at(first))} ~ ${md(at(last))}` : `총 0회`,
      aiRange: list.length ? `1~${last.session_number}회차` : DASH,
      flow: flow.length ? flow : [{ k: DASH, t: DASH, d: '' }],
      hasBars: bars.length > 0,
      bars,
      count: String(list.length),
      ses,
      loadErr,
    };
  }
}

export default function AppHistory(props) {
  const app = useAppData();
  const { caseId } = useIds();
  const main = useAsync(async () => {
    if (!app.userId || !caseId) return null;
    const [c, page, history, timeline] = await Promise.all([
      cases.get(caseId),
      soft(cases.listSessions(caseId, { page_size: 100 })),
      soft(senior.history(caseId)),
      soft(senior.domainTimeline(caseId)),
    ]);
    const sessions = page ? [...page.items].sort((a, b) => b.session_number - a.session_number) : [];
    return { c, sessions, history, timeline };
  }, [app.userId, caseId]);
  let loadErr = '';
  if (!caseId) loadErr = '대상자를 고르지 않았어요. 대상자 목록에서 다시 들어와 주세요.';
  else if (main.error) loadErr = main.error.message || '이전 상담을 불러오지 못했어요.';
  const v = useDC(Logic, { ...props, app, data: main.data, loadErr });
  return <View v={v} />;
}
