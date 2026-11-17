// 상담사 앱(폰) · 메모 — 디자인 AppMemo.dc.html.
// 서버 연결: 상담사 메모 API(GET · POST · PATCH · DELETE /memos, API_CONTRACT 25절) — 아동 앱과 같은 API. 쓴 사람만 본다.
//  - 관련 어르신: 내 진행 중 고령자 사례(App.parts). 주소에 ?case= 가 있으면 그 대상자를 골라 둔다.
//  - 목록: 최신순 100개. 칩은 메모에 붙은 사례의 별칭(서버 값), 시각은 이 폰 시각('방금' · '오늘 15:20' …).
//  - 서버가 풀지 못한 메모(unreadable)는 '지금은 읽을 수 없어요' 로 보인다.
//  - 저장 · 수정 · 삭제가 실패하면 적은 글은 칸에 그대로 두고 오류 줄을 보인다.
import { useState } from 'react';
import { useDC } from '../dc';
import DesignLogic from '../design/AppMemo.logic';
import { memos } from '@cw/api/endpoints';
import { useAsync } from '../data/useAsync';
import { useIds } from '../data/nav';
import { useAppData, withApp, elderOpts, whenText, msOf } from './App.parts';
import View from './AppMemo.view';

const UNREADABLE = '지금은 읽을 수 없어요. 관리자에게 알려 주세요.';
const errText = (e, fb) => (e && e.message) || fb;

class Logic extends withApp(DesignLogic) {
  constructor(props) {
    super(props);
    this.state = { ...this.state, nChild: props.initCase || '', busy: false, err: '' };
  }

  // 디자인의 localStorage 메모(예시 3개) 대신 서버 메모.
  mRead() {
    return (this.props.list || []).map((m) => ({
      id: m.id,
      elder: m.case_id || '',
      alias: m.child_alias || '',
      text: m.unreadable || m.text == null ? UNREADABLE : m.text,
      t: whenText(msOf(m.created_at)),
    }));
  }

  mWrite() {}

  run(call, ok, fb) {
    if (this.state.busy) return;
    this.setState({ busy: true, err: '' });
    call().then(
      () => {
        this.setState({ busy: false, ...ok });
        this.props.reload();
      },
      (e) => this.setState({ busy: false, err: errText(e, fb) }),
    );
  }

  renderVals() {
    const v = super.renderVals();
    const s = this.state;
    const M = this.mRead();
    const opts = elderOpts(this.props.app).filter((o) => o.v);
    return {
      ...v,
      elderOpts: opts,
      memos: M.map((m) => ({
        elder: m.alias, hasChild: !!m.alias, t: m.t, text: m.text,
        open: () => this.setState({ edit: { id: m.id, elder: m.elder, text: m.text === UNREADABLE ? '' : m.text, t: m.t }, ask: false, err: '' }),
      })),
      count: String(this.props.total),
      add: () => {
        const t = (s.nText || '').trim();
        if (!t) return;
        this.run(() => memos.create({ text: t, case_id: s.nChild || null }), { nText: '' }, '메모를 저장하지 못했어요. 연결을 확인하고 다시 눌러 주세요.');
      },
      saveEdit: () => {
        const ed = this.state.edit;
        const t = (ed.text || '').trim();
        if (!t) return;
        this.run(() => memos.update(ed.id, { text: t, case_id: ed.elder || null }), { edit: null }, '메모를 고치지 못했어요. 잠시 뒤 다시 해 주세요.');
      },
      del: () => {
        const ed = this.state.edit;
        this.run(() => memos.remove(ed.id), { edit: null, ask: false }, '메모를 지우지 못했어요. 잠시 뒤 다시 해 주세요.');
      },
      shClose: () => this.setState({ edit: null, ask: false, err: '' }),
      msg: s.err || this.props.loadErr || '',
    };
  }
}

export default function AppMemo(props) {
  const app = useAppData();
  const { caseId } = useIds();
  const list = useAsync(() => (app.userId ? memos.list({ page: 1, page_size: 100 }) : null), [app.userId]);
  const loadErr = list.error ? errText(list.error, '메모를 불러오지 못했어요.') : app.eldersErr;
  const v = useDC(Logic, {
    ...props, app, initCase: caseId, list: list.data ? list.data.items : [], total: list.data ? list.data.meta.total : 0, reload: list.reload, loadErr,
  });
  return <View v={v} />;
}
