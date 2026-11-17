// 법령 · 매뉴얼 — 디자인 LawGuide.dc.html.
//  - '업무 단계별 참고사항 · 주요 조문' 은 디자인 글 그대로 둔다(노인복지법 · 사업안내 · 109 · 1577-1389 같은 공공 정보, 국가법령정보센터 링크).
//    다만 호칭 예시의 예시 이름(김순자)은 '○○○' 로 바꿨다.
//  - 'AI 에게 묻기' 는 디자인의 정해진 답(낱말 맞추기) 대신 '준비 중' 안내로 답한다. 서버 law-guide 는 아동 법령 · 매뉴얼 기준이라
//    고령자 문서 RAG 가 준비될 때까지 부르지 않는다. 질문은 서버로 보내지 않는다.
import { useDC } from '../dc';
import DesignLogic from '../design/LawGuide.logic';
import { useShell } from '../data/useShell';
import View from './LawGuide.view';

const GREETING =
  '고령자 법령 · 지침 AI 질의는 준비 중이에요.\n지금은 \'업무 단계별 참고사항 · 주요 조문\' 탭에서 노인복지법 · 사업안내 요약과 국가법령정보센터 원문 링크를 확인해 주세요.';
const NOT_READY =
  '아직 답할 수 없어요 — 고령자 법령 · 지침 문서로 답하는 기능은 준비 중이에요. \'업무 단계별 참고사항 · 주요 조문\' 탭에서 찾아보시거나, 조문은 국가법령정보센터 원문으로 확인해 주세요.';
const unExample = (t) => (typeof t === 'string' ? t.split('"김순자 님"').join('"○○○ 님"') : t);

class Logic extends DesignLogic {
  constructor(props) {
    super(props);
    this.state = { ...this.state, msgs: [{ role: 'bot', text: GREETING }] };
  }

  renderValsBase() {
    const base = super.renderValsBase();
    const ask = (q) => {
      const text = String(q || '').trim();
      if (!text) return;
      this._msgScroll = true;
      this.setState({ msgs: [...this.state.msgs, { role: 'me', text }, { role: 'bot', text: NOT_READY }], draft: '' });
    };
    const msgs = this.state.msgs.map((m) => ({ cls: m.role === 'me' ? 'lg-u' : 'lg-b', text: m.text, refs: [], laws: [], hasRefs: false }));
    const refs = (base.refs || []).map((r) => ({ ...r, sum: unExample(r.sum), items: (r.items || []).map(unExample) }));
    return {
      ...base,
      ...this.props.shell,
      msgs,
      refs,
      typing: false,
      suggs: (base.suggs || []).map((x) => ({ ...x, ask: () => ask(x.label) })),
      submit: (e) => {
        if (e && e.preventDefault) e.preventDefault();
        ask(this.state.draft);
      },
      chatReset: () => this.setState({ msgs: [this.state.msgs[0]], draft: '' }),
    };
  }

  renderVals() {
    return { ...super.renderVals(), navLinkCnt: '', navFollowCnt: '' };
  }
}

export default function LawGuide(props) {
  const shell = useShell();
  const v = useDC(Logic, { ...props, shell });
  return <View v={v} />;
}
