// 1단계 기록 확인 — 디자인 Step1Record.dc.html. 회차 원문(STT)을 보고 · 듣고 · 고친 뒤 확정하고, 회차 통합 요약 분석을 시작한다.
//  - 원문: GET /sessions/{id}/transcript. 변환 중(STT_PROCESSING)이면 2.5초마다 다시 읽는다.
//  - 고치기: '전체 STT 보기' 에서 문장, 화자 단추로 화자. 모아 두었다가 '정서·위기 신호 확인 →' 을 누르면
//    PATCH(바꾼 발화의 바꾼 칸만) → POST confirm → POST analysis(202) 하고 2단계로 간다. 이미 확정한 원문은 고칠 수 없다(읽기만).
//  - 기본 보기는 전체 STT. 고령자 회차는 1차 핵심 발화 스캔을 하지 않으므로(key_scan SKIPPED) 디자인의 '1차 임시 핵심 발화' 자리는
//    '어르신 발화'(상담사가 아닌 화자) 모아 보기로 쓴다.
//  - 확인 필요 구간: 신뢰도 0 < c < 0.7(API_CONTRACT 7절). '확인' 단추는 이 화면 안의 표시만(서버 저장 없음).
//  - 목소리 신호 · 확인 서식(S-0x) · 음향 분석 제외는 고령자 서버 값이 없어 표시하지 않는다.
//  - 재생: @cw/data useSessionAudio + useAudioPlayer(GET /sessions/{id}/audio/file).
import { useCallback, useEffect, useRef, useState } from 'react';
import { useDC } from '../dc';
import DesignLogic from '../design/Step1Record.logic';
import { analysis, cases, transcript } from '@cw/api/endpoints';
import { CONSULTATION_TYPE_LABELS } from '@cw/api/types';
import { useSessionAudio } from '@cw/data/useSessionAudio';
import { useAudioPlayer } from '@cw/data/useAudioPlayer';
import { errorMessage } from '@cw/data/useRemote';
import { parseBackendTime } from '@cw/data/time';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { href, useIds } from '../data/nav';
import { DASH } from '../data/format';
import View from './Step1Record.view';

const SPK = { CHILD: '어르신(내담자)', COUNSELOR: '상담사', GUARDIAN: '가족(보호자)', OTHER: '기타', UNKNOWN: '화자?' };
const SPK_ORDER = ['CHILD', 'COUNSELOR', 'GUARDIAN', 'OTHER', 'UNKNOWN'];
const DAYS = ['일', '월', '화', '수', '목', '금', '토'];
const POLL_MS = 2500;

const pad = (n) => String(n).padStart(2, '0');
const clock = (ms) => { const t = Math.max(0, Math.floor((ms || 0) / 1000)); return `${pad(Math.floor(t / 60))}:${pad(t % 60)}`; };
const isLow = (c) => c > 0 && c < 0.7;

function sessionSub(row) {
  if (!row) return DASH;
  const d = parseBackendTime(row.consulted_at || row.created_at);
  const kind = row.consultation_type ? CONSULTATION_TYPE_LABELS[row.consultation_type] : row.title || '상담';
  return d ? `${d.getMonth() + 1}/${d.getDate()}(${DAYS[d.getDay()]}) ${kind}` : kind;
}

/** 원문 읽기. 변환 중이면 되풀이해 읽는다. */
function useTranscript(sessionId, ready) {
  const [state, setState] = useState({ env: null, error: null, loading: true });
  const seq = useRef(0);
  const load = useCallback(() => {
    if (!ready || !sessionId) return;
    const id = ++seq.current;
    transcript.get(sessionId).then(
      (env) => {
        if (id !== seq.current) return;
        setState({ env, error: null, loading: false });
        if (env.session_status === 'STT_PROCESSING') setTimeout(() => id === seq.current && load(), POLL_MS);
      },
      (error) => id === seq.current && setState((s) => ({ ...s, error, loading: false })),
    );
  }, [sessionId, ready]);
  useEffect(() => {
    load();
    return () => { seq.current += 1; };
  }, [load]);
  return { ...state, reload: load, set: (env) => { seq.current += 1; setState({ env, error: null, loading: false }); } };
}

class Logic extends DesignLogic {
  constructor(props) {
    super(props);
    this.state = { ...this.state, view: 'all', sp: {}, tx: {}, ok: {}, busy: false, err: '' };
  }

  // 회차 고르기: 이 사례의 실제 회차들
  slVals() {
    const { sesList, ids } = this.props;
    const rows = sesList.data ? [...sesList.data.items].sort((a, b) => b.session_number - a.session_number) : [];
    const cur = rows.find((r) => r.id === ids.sessionId);
    const open = !!(this.state && this.state.__slOpen);
    return {
      slOpen: open, slExp: open ? 'true' : 'false', slToggle: () => this.setState({ __slOpen: !open }), slBtn: '회차 선택',
      slNo: cur ? `${cur.session_number}회차` : DASH, slSub: sessionSub(cur),
      slItems: rows.map((r) => ({
        no: `${r.session_number}회차`, meta: sessionSub(r),
        st: r.status === 'APPROVED' ? '확정' : r.status === 'CREATED' ? '녹취 전' : '처리 중',
        stCls: r.status === 'APPROVED' ? 'chip c-ok' : 'chip c-check',
        on: r.id === ids.sessionId ? 'true' : 'false', cls: r.id === ids.sessionId ? 'on' : '',
        pick: () => { this.setState({ __slOpen: false, sp: {}, tx: {}, ok: {}, err: '' }); window.location.hash = href('Step1Record', { caseId: ids.caseId, sessionId: r.id }); },
      })),
    };
  }

  renderVals() {
    const v = super.renderVals();
    const { ids } = this.props;
    return {
      ...v,
      markBack: () => {
        const back = href('Step1Record', ids);
        try { window.localStorage.setItem('ispot-back', back); } catch (e) {}
        try { window.sessionStorage.setItem('ispot-back', back); } catch (e) {}
        window.__ispotBack = back;
      },
    };
  }

  renderValsBase() {
    const base = super.renderValsBase();
    const s = this.state;
    const { shell, ids, caseQ, sesList, tx, player } = this.props;
    const env = tx.env;
    const t = env && env.transcript;
    const status = env ? env.session_status : null;
    const confirmed = !!(t && t.is_confirmed);
    const segs = t ? t.segments : [];
    const edited = new Set(t ? t.edited_segment_ids || [] : []);
    const spOf = (g) => s.sp[g.segment_id] || g.speaker;
    const all = segs.map((g, i) => ({ g, i, low: isLow(g.confidence) }));
    const pick = s.view === 'all' ? all : s.view === 'low' ? all.filter((l) => l.low) : all.filter((l) => spOf(l.g) !== 'COUNSELOR');

    const cnt = {}; const numOf = {};
    all.forEach(({ g }) => { const k = spOf(g); if (k === 'UNKNOWN') return; cnt[k] = (cnt[k] || 0) + 1; numOf[g.segment_id] = cnt[k]; });

    const lines = pick.map(({ g, low }) => {
      const id = g.segment_id;
      const done = !!s.ok[id];
      const edit = !confirmed && (s.view === 'all' || (s.view === 'low' && low));
      const sp = spOf(g);
      const spName = SPK[sp] || sp;
      const open = s.spOpen === id;
      const text = s.tx[id] !== undefined ? s.tx[id] : g.text;
      const tLabel = clock(g.start_ms);
      const spOpts = SPK_ORDER.map((o) => ({
        label: SPK[o], sel: o === sp ? 'true' : 'false', cls: o === sp ? 'spopt on' : 'spopt',
        pick: () => { const next = { ...this.state.sp }; if (o === g.speaker) delete next[id]; else next[id] = o; this.setState({ sp: next, spOpen: null }); },
      }));
      const changedHere = s.tx[id] !== undefined || !!s.sp[id];
      return {
        lid: 'ln-' + tLabel.replace(':', ''), ring: s.focusT === tLabel ? 'inset 0 0 0 2px #5FA4D6' : 'none', t: tLabel,
        play: () => { this.setState({ focusT: tLabel }); player.playFrom(g.start_ms); },
        laws: [], hasLaws: false, cues: [], hasCues: false, hold: '', hasHold: false,
        sp: spName, text, aria: `${tLabel} 발화 고치기`, spFw: sp === 'CHILD' ? 700 : 500,
        spFix: !!s.sp[id],
        spLabel: numOf[id] ? `${spName} ${numOf[id]}` : spName, spMenu: open, spDir: open && s.spUp ? 'up' : '', spExp: open ? 'true' : 'false', spOpts,
        toggleSp: confirmed ? () => {} : (e) => {
          if (open) { this.setState({ spOpen: null }); return; }
          let up = false;
          try { const r = e.currentTarget.getBoundingClientRect(); up = (window.innerHeight - r.bottom) < 180 && r.top > 180; } catch (er) {}
          this.setState({ spOpen: id, spUp: up });
        },
        conf: g.confidence > 0 ? `${Math.round(g.confidence * 100)}%` : DASH,
        edit, read: !edit,
        change: (e) => this.setState({ tx: { ...this.state.tx, [id]: e.target.value }, err: '' }),
        hint: done ? '확인했어요' : changedHere ? '고침 · 저장 전' : low ? '신뢰도가 낮아요 · 시간을 눌러 다시 들어 보세요' : edited.has(id) ? '상담사 수정' : '',
        hintFg: '#66788A',
        bg: low && !done && s.view !== 'key' ? '#C0DEF0' : '#FFFFFF',
        okLabel: done ? '확인됨 ✓' : '확인', ok: () => this.setState({ ok: { ...this.state.ok, [id]: !done } }),
      };
    });
    const lowLeft = all.filter((l) => l.low && !s.ok[l.g.segment_id]).length;
    const titles = { key: '어르신 발화', all: '전체 STT', low: '확인 필요 구간' };

    // 재생 바
    const lastEnd = segs.length ? segs[segs.length - 1].end_ms : 0;
    const durMs = player.durationMs || lastEnd || 0;
    const durS = Math.max(1, Math.round(durMs / 1000));
    const posS = Math.min(durS, Math.floor(player.currentMs / 1000));
    const plMarks = all.filter((l) => l.low && !s.ok[l.g.segment_id]).map((l) => {
      const tl = clock(l.g.start_ms);
      return { t: tl, left: `${Math.min(100, (l.g.start_ms / Math.max(1, durMs)) * 100)}%`, go: () => { this._scrollTo = tl; this.setState({ view: 'low', focusT: tl }); player.seek(l.g.start_ms); } };
    });

    // 상태 줄(변환 중 · 실패 · 저장 오류 · 재생 안내)
    let statusMsg = '';
    if (!ids.sessionId) statusMsg = '회차가 정해지지 않았어요. 사례 화면에서 회차를 골라 들어와 주세요.';
    else if (tx.error) statusMsg = errorMessage(tx.error, '원문을 불러오지 못했습니다.');
    else if (status === 'STT_PROCESSING') statusMsg = '원문으로 바꾸는 중이에요… 끝나면 바로 보여 드려요.';
    else if (status === 'STT_FAILED') statusMsg = (env.error && env.error.message) || '원문 변환에 실패했습니다. 녹취를 다시 올려 주세요.';
    else if (status === 'CREATED') statusMsg = '아직 녹취가 없어요. 녹취 · 자료 올리기에서 올려 주세요.';
    else if (status === 'AUDIO_UPLOADED' && !t) statusMsg = '녹취는 올렸지만 원문 변환을 아직 시작하지 않았어요. 녹취 · 자료 올리기에서 다시 올려 주세요.';
    else if (tx.loading && !env) statusMsg = '불러오는 중…';
    if (s.err) statusMsg = s.err;
    else if (s.busy) statusMsg = s.busyMsg || '저장하는 중…';
    else if (!statusMsg && (player.error || player.notice)) statusMsg = player.error || player.notice;

    // 확정 → 분석 시작 → 2단계
    const step2Href = href('Step2Signals', ids);
    const goStep2 = async (e) => {
      if (e && e.preventDefault) e.preventDefault();
      if (this.state.busy || !t) return;
      const st = this.state;
      try {
        if (!t.is_confirmed) {
          const changes = segs
            .filter((g) => st.tx[g.segment_id] !== undefined || st.sp[g.segment_id])
            .map((g) => {
              const out = { segment_id: g.segment_id };
              if (st.tx[g.segment_id] !== undefined && st.tx[g.segment_id].trim() !== g.text) out.text = st.tx[g.segment_id].trim();
              if (st.sp[g.segment_id] && st.sp[g.segment_id] !== g.speaker) out.speaker = st.sp[g.segment_id];
              return out;
            })
            .filter((c) => c.text !== undefined || c.speaker);
          if (changes.some((c) => c.text === '')) { this.setState({ err: '빈 문장은 저장할 수 없어요. 내용을 넣어 주세요.' }); return; }
          if (changes.length) {
            this.setState({ busy: true, busyMsg: '고친 내용을 저장하는 중…', err: '' });
            await transcript.update(ids.sessionId, { segments: changes });
          }
          this.setState({ busy: true, busyMsg: '원문을 확정하는 중…', err: '' });
          await transcript.confirm(ids.sessionId);
          this.setState({ sp: {}, tx: {} });
        }
        const now = await transcript.get(ids.sessionId);
        if (now.session_status === 'STT_CONFIRMED' || now.session_status === 'AI_FAILED') {
          this.setState({ busy: true, busyMsg: '통합 요약 분석을 시작하는 중…', err: '' });
          await analysis.run(ids.sessionId);
        }
        this.setState({ busy: false });
        window.location.hash = step2Href;
      } catch (caught) {
        this.setState({ busy: false, err: errorMessage(caught, '저장하지 못했습니다. 잠시 후 다시 시도해 주세요.') });
        tx.reload();
      }
    };

    const c = caseQ.data;
    const caseName = c ? c.child_alias || DASH : DASH;
    const total = sesList.data ? sesList.data.meta.total : null;

    return {
      ...base, ...shell,
      lines, lowLeft: lowLeft + '곳', viewTitle: titles[s.view],
      chipText: confirmed ? '확정됨' : s.view === 'key' ? '검수 전' : (lowLeft ? `확인 필요 ${lowLeft}` : '모두 확인'),
      chipCls: confirmed ? 'chip c-ok' : s.view === 'key' ? 'chip c-sand' : (lowLeft ? 'chip c-check' : 'chip c-ok'),
      boxCls: s.view === 'all' ? 'scroll' : '', allCls: s.view === 'all' ? 'btn-p' : 'btn-s', lowCls: s.view === 'low' ? 'btn-p' : 'btn-s',
      xaShow: false, xaItems: [], xaText: '',
      done: !!t, analyzing: false,
      plMarks, plHasMarks: lowLeft > 0, plMarkCount: lowLeft,
      plOn: player.playing, plOff: !player.playing, plPlayLabel: player.playing ? '일시정지' : '재생',
      plPos: posS, plMax: durS, plPct: `${(posS / durS) * 100}%`, plCur: clock(player.currentMs), plDur: durMs ? clock(durMs) : '--:--',
      plToggle: () => player.toggle(), plStop: () => player.stop(),
      plBack: () => player.skip(-5000), plFwd: () => player.skip(5000),
      plSeek: (e) => player.seek((Number(e.target.value) || 0) * 1000),
      statusMsg, hasStatus: !!statusMsg,
      caseName, caseCrumb: c ? `${caseName} ${c.case_number || ''}`.trim() : DASH,
      slHead: `${caseName} · 총 ${total === null ? DASH : total}회`,
      caseHref: href('CaseInfo', { caseId: ids.caseId }), historyHref: href('CaseHistory', { caseId: ids.caseId }),
      detailHref: href('SessionDetail', ids),
      step1Href: href('Step1Record', ids), step2Href, step3Href: href('Step3Summary', ids), step4Href: href('Step4Next', ids),
      goStep2, nextLabel: s.busy ? '처리하는 중…' : confirmed ? '정서·위기 신호 확인 →' : '확정 · 정서·위기 신호 확인 →',
    };
  }
}

export default function Step1Record(props) {
  const shell = useShell();
  const ids = useIds();
  const caseQ = useAsync(() => (shell.ready && ids.caseId ? cases.get(ids.caseId) : null), [shell.ready, ids.caseId]);
  const sesList = useAsync(() => (shell.ready && ids.caseId ? cases.listSessions(ids.caseId, { page: 1, page_size: 100 }) : null), [shell.ready, ids.caseId]);
  const tx = useTranscript(ids.sessionId, shell.ready);
  const audio = useSessionAudio(ids.sessionId, { enabled: shell.ready && !!(tx.env && tx.env.transcript) });
  const player = useAudioPlayer(audio);
  const v = useDC(Logic, { ...props, shell, ids, caseQ, sesList, tx, player });
  return <View v={v} />;
}
