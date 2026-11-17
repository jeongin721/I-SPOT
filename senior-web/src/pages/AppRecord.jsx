// 상담사 앱(폰) · 녹음 — 디자인 AppRecord.dc.html. counselor-web 의 폰 녹음기(useRecorder) · 대기열(appRecordings) 그대로.
//  - 어르신: 내 진행 중 고령자 사례(App.parts). 주소에 ?case= 가 있으면 그 대상자를 골라 둔다(대상자 목록 · 다음 상담 준비 · 일정의 '녹음 시작').
//  - 회차: 고른 대상자의 회차 중 녹음을 올릴 수 있는 것(빈 회차 · 녹음만 있는 회차 · 변환 실패 회차) + '새 회차'.
//    '새 회차' 면 올릴 때 회차를 만든다(상담 일시 = 녹음 시작 시각, 상담 유형 = 고른 값).
//  - 상담 유형: 디자인 4개 그대로. 서버 값으로 바꿔 보낸다(내방상담 = 기관 면담 OFFICE).
//  - 저장하고 올리기: 녹음을 이 브라우저(IndexedDB)에 저장한 뒤 회차 만들기 → 음성 올리기 → 원문 변환 요청.
//    웹에서 같은 대상자 · 회차를 열면 녹음이 있고, 변환이 끝나면 1단계(기록 확인)부터 이어서 한다.
//  - 마이크 · 녹음 도구 오류(권한 거부 · 지원 안 함 등)는 녹음 칸 위 오류 줄에 보인다.
//  - 맨 아래 '이 시안은…' 문구는 실제 동작 안내로 바꿨다(화면을 닫으면 다음에 열 때 이어서 올린다 — 웹 앱이라).
import { useEffect, useState } from 'react';
import { useDC } from '../dc';
import DesignLogic from '../design/AppRecord.logic';
import { cases } from '@cw/api/endpoints';
import { fileNameFor, finishDraft } from '@cw/data/appRecordings';
import {
  clearRecording, preloadRecorder, pauseRecording, resetRecording, resumeRecording, setRecorderError, startRecording, stopRecording, useRecorder,
} from '@cw/data/useRecorder';
import { useIds } from '../data/nav';
import { useAppData, withApp, elderOpts, nameOf, sessionKind } from './App.parts';
import View from './AppRecord.view';

const KIND_CODE = { 정기상담: 'REGULAR', 방문상담: 'VISIT', 전화상담: 'PHONE', 내방상담: 'OFFICE' };
const KIND_LABEL = { REGULAR: '정기상담', VISIT: '방문상담', PHONE: '전화상담', OFFICE: '내방상담' };
const UPLOADABLE = new Set(['CREATED', 'AUDIO_UPLOADED', 'STT_FAILED']);
const ST = { idle: '녹음 대기', rec: '녹음 중', paused: '일시정지', done: '녹음 완료', saved: '저장 완료' };

function mmss(ms) {
  const s = Math.floor((ms || 0) / 1000);
  const h = Math.floor(s / 3600);
  const m = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  return h > 0 ? `${h}:${m}:${ss}` : `${m}:${ss}`;
}

function useUploadableSessions(caseId) {
  const [state, setState] = useState({ caseId: null, rows: [] });
  useEffect(() => {
    if (!caseId) return undefined;
    let live = true;
    cases
      .listSessions(caseId, { page: 1, page_size: 100 })
      .then((page) => {
        if (!live) return;
        const rows = page.items.filter((r) => UPLOADABLE.has(r.status) && r.source !== 'DOCUMENT').sort((a, b) => b.session_number - a.session_number);
        setState({ caseId, rows });
      })
      .catch(() => live && setState({ caseId, rows: [] }));
    return () => {
      live = false;
    };
  }, [caseId]);
  return state.caseId === caseId ? state.rows : [];
}

class Logic extends withApp(DesignLogic) {
  // 디자인의 '다른 화면에서 고른 어르신' localStorage 토큰 대신 주소의 ?case= 를 쓴다.
  recTok() {}

  recTick() {}

  renderVals() {
    const v = super.renderVals();
    const s = this.state;
    const { app, rec, sel, setCase, sessionRows } = this.props;
    const draft = rec.draft;
    const caseId = sel.caseId;
    const elder = app.elders.find((c) => c.id === caseId);
    const ses = sel.ses;
    const session = sessionRows.find((r) => r.id === ses);
    const kindLabel = sel.kind;
    const savedItem = s.savedId ? this.qItems().find((x) => x.id === s.savedId) : null;
    const phase = s.savedId && rec.phase === 'idle' ? 'saved' : rec.phase;
    const lock = phase !== 'idle' || !!s.saving;
    const qs = savedItem ? (savedItem.status === 'wait' ? 'run' : savedItem.status) : s.savedId && app.rec.loaded ? 'done' : 'run';
    const opts = elderOpts(app);
    if (draft && !elder) opts.unshift({ v: draft.caseId, label: draft.childLabel });

    const start = async () => {
      if (!this.state.con) {
        this.setState({ err: true });
        return;
      }
      if (!elder || !app.userId) return;
      // 녹음이 있는 회차를 고르면 바꿀지 한 번 묻는다(폰에서는 잘못 고르기 쉬워서).
      if (session && session.status !== 'CREATED' && !window.confirm('이 회차에는 이미 녹음이 있어요. 바꿀까요?')) return;
      this.setState({ savedId: null });
      await startRecording({
        userId: app.userId,
        caseId: elder.id,
        childLabel: nameOf(elder),
        sessionId: ses === 'new' ? null : ses,
        sessionNumber: session ? session.session_number : null,
        expectStatus: session ? session.status : 'CREATED',
        consultationType: KIND_CODE[kindLabel] || 'REGULAR',
        consultedAt: new Date().toISOString(),
      });
    };
    const save = async () => {
      if (!draft || this.state.saving) return;
      this.setState({ saving: true });
      try {
        const id = await finishDraft(draft, fileNameFor(draft, KIND_LABEL[draft.consultationType] || sessionKind(draft.consultationType)), rec.elapsedMs);
        clearRecording();
        this.setState({ savedId: id, con: false, saving: false });
      } catch {
        setRecorderError('폰에 녹음을 저장하지 못했어요. 저장 공간을 확인한 뒤 다시 눌러 주세요.');
        this.setState({ saving: false });
      }
    };
    const reset = () => {
      if (phase === 'saved') {
        this.setState({ savedId: null, con: false });
        return;
      }
      resetRecording();
      this.setState({ con: false });
    };
    const sesLabel = (it) => (it && it.sessionNumber ? `${it.sessionNumber}회차` : '새 회차');

    return {
      ...v,
      elderOpts: opts,
      elder: draft ? draft.caseId : caseId || '',
      setChild: (ev) => setCase({ caseId: ev.target.value, ses: 'new' }),
      ses: draft ? draft.sessionId || 'new' : ses,
      setSes: (ev) => setCase({ ses: ev.target.value }),
      sesOpts: sessionRows.map((r) => ({ v: r.id, label: `${r.session_number}회차${r.status === 'CREATED' ? '' : ' · 녹음 바꾸기'}` })),
      kind: draft ? KIND_LABEL[draft.consultationType] || '정기상담' : kindLabel,
      setKind: (ev) => setCase({ kind: ev.target.value }),
      lock,
      setCon: (ev) => this.setState({ con: !!ev.target.checked, err: false }),
      status: ST[phase],
      dotCls: phase === 'rec' ? 'rdot live' : 'rdot',
      time: mmss(phase === 'saved' ? (savedItem ? savedItem.durationMs : 0) : rec.elapsedMs),
      idle: phase === 'idle',
      running: phase === 'rec' || phase === 'paused',
      done: phase === 'done',
      saved: phase === 'saved',
      start: () => void start(),
      pauseLabel: phase === 'paused' ? '계속' : '일시정지',
      pause: () => (phase === 'paused' ? void resumeRecording() : pauseRecording()),
      stopRec: () => void stopRecording(),
      reset,
      save: () => void save(),
      summary: savedItem ? `${savedItem.childLabel} · ${sesLabel(savedItem)} · ${KIND_LABEL[savedItem.consultationType] || sessionKind(savedItem.consultationType)} · ${mmss(savedItem.durationMs)}` : '',
      upRun: qs === 'run',
      upDone: qs === 'done',
      upFail: qs === 'fail',
      upFailText: savedItem && savedItem.needNewSession ? savedItem.error : '업로드 실패 · 연결이 돌아오면 다시 올려 주세요',
      upRunText: '업로드 중이에요. 화면을 닫으면 다음에 열 때 이어서 올려요.',
      footNote:
        "녹음하는 동안에는 화면을 켜 두세요. 전화 · 화면 꺼짐으로 마이크가 끊기면 일시정지되고, '계속' 을 누르면 같은 녹음에 이어서 녹음해요. 녹음은 이 휴대폰에 먼저 저장한 뒤 올리고, 연결이 끊기면 다시 연결될 때 자동으로 다시 올려요. 올린 녹음은 웹의 같은 대상자 · 회차에서 이어서 확인할 수 있어요.",
      msg: rec.error || app.eldersErr || '',
    };
  }
}

export default function AppRecord(props) {
  const app = useAppData();
  const rec = useRecorder();
  // 변환 도구를 미리 받아 둔다(녹음 시작을 누른 순간 기다리지 않게).
  useEffect(() => preloadRecorder(), []);
  const { caseId: want } = useIds();
  const [sel, setSel] = useState({ caseId: null, ses: 'new', kind: '정기상담' });
  useEffect(() => {
    if (sel.caseId || app.elders.length === 0) return;
    setSel((x) => ({ ...x, caseId: app.elders.some((c) => c.id === want) ? want : app.elders[0].id }));
  }, [app.elders, sel.caseId, want]);
  const setCase = (patch) => setSel((x) => ({ ...x, ...patch }));
  const sessionRows = useUploadableSessions(rec.draft ? rec.draft.caseId : sel.caseId);
  const v = useDC(Logic, { ...props, app, rec, sel, setCase, sessionRows });
  return <View v={v} />;
}
