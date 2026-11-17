// 상담사 앱(폰) · 업로드 — 디자인 AppUpload.dc.html.
//  - 어르신 선택: 내 진행 중 고령자 사례(App.parts). 주소에 ?case= 가 있으면 그 대상자를 골라 둔다(대상자 목록의 '자료 올리기').
//  - 자료 올리기 › 파일: 음성 파일(.m4a · .mp3 · .wav 등)이면 고른 대상자의 새 회차로 올리고 원문 변환까지 요청한다
//    (counselor-web 의 폰 대기열 appRecordings 그대로 — 이 브라우저에 먼저 저장 → 회차 만들기 → 음성 올리기 → 변환 요청).
//    웹에서 같은 대상자 · 회차를 열면 녹음이 있고, 변환이 끝나면 1단계(기록 확인)부터 이어서 한다.
//  - 사진 · 문서: 사례에 붙일 서버 자리(대상자 파일함)가 아직 없어 '준비 중' 안내만.
//  - 올린 자료: 이 폰의 대기열. 실패하면 '다시 올리기'(새 회차를 이미 만들었으면 다시 만들지 않는다). '지우기' 는 폰에서만 지운다.
//    다 올린 줄은 그 회차의 지금 상태('웹: 원문 검수 필요' 등)를 시각 뒤에 붙인다. 웹에서 지운 회차의 줄은 목록에서 뺀다.
import { useEffect, useState } from 'react';
import { useDC } from '../dc';
import DesignLogic from '../design/AppUpload.logic';
import { enqueueAudioFile, removeRecording, syncDoneWithServer } from '@cw/data/appRecordings';
import { checkAudioFile, readAudioDuration } from '@cw/data/audioFile';
import { SESSION_STATUS_LABELS } from '@cw/data/sessionRows';
import { useIds } from '../data/nav';
import { useAppData, withApp, elderOpts, nameOf } from './App.parts';
import View from './AppUpload.view';

class Logic extends withApp(DesignLogic) {
  async pick(fl) {
    const { app } = this.props;
    const caseId = this.caseId();
    const elder = app.elders.find((c) => c.id === caseId);
    const isAudio = /^audio\//.test(fl.type) || /\.(m4a|mp3|wav|ogg|flac|webm|mp4|aac)$/i.test(fl.name);
    if (!isAudio) {
      this.setState({ err: '사진 · 문서 올리기는 준비 중이에요. 지금은 녹음(음성 파일)만 올릴 수 있어요.' });
      return;
    }
    const problem = checkAudioFile(fl);
    if (problem) {
      this.setState({ err: problem });
      return;
    }
    if (!elder || !app.userId) {
      this.setState({ err: '어르신을 먼저 골라 주세요.' });
      return;
    }
    const durationMs = await readAudioDuration(fl);
    try {
      await enqueueAudioFile({ userId: app.userId, caseId: elder.id, childLabel: nameOf(elder), file: fl, durationMs });
    } catch {
      this.setState({ err: '폰에 파일을 저장하지 못했어요. 저장 공간을 확인해 주세요.' });
    }
  }

  caseId() {
    const { app, initCase } = this.props;
    const want = this.state.caseId || initCase;
    if (want && app.elders.some((c) => c.id === want)) return want;
    return app.elders[0] ? app.elders[0].id : '';
  }

  renderVals() {
    const v = super.renderVals();
    const { app, statuses } = this.props;
    const raw = this.qItems();
    const rows = this.qRead();
    return {
      ...v,
      elderOpts: elderOpts(app),
      elder: this.caseId(),
      setChild: (ev) => this.setState({ caseId: ev.target.value, err: '' }),
      pickFile: (ev) => {
        const fl = ev && ev.target && ev.target.files && ev.target.files[0];
        try {
          ev.target.value = '';
        } catch (e) {
          // 일부 브라우저
        }
        if (!fl) return;
        this.setState({ pk: false, err: '' });
        void this.pick(fl);
      },
      items: rows.map((x, i) => {
        const st = x.status === 'done' && statuses[x.id];
        return {
          name: x.name, kind: x.kind, who: x.who, size: x.size,
          t: st ? `${x.t} · 웹: ${SESSION_STATUS_LABELS[st] || st}` : x.t,
          err: x.err || '', cls: x.status === 'fail' ? 'card qi f' : 'card qi',
          st: x.status === 'fail' ? '실패' : x.status === 'run' ? '올리는 중' : '완료',
          stCls: x.status === 'fail' ? 'chip red' : x.status === 'run' ? 'chip gold' : 'chip',
          run: x.status === 'run', fail: x.status === 'fail',
          retry: () => this.qRetry(x.id),
          remove: () => {
            if (window.confirm('이 녹음을 폰에서 지울까요? 아직 서버에 올라가지 않은 녹음은 되살릴 수 없어요.')) void removeRecording(raw[i].id);
          },
        };
      }),
      msg: this.state.err || app.eldersErr || (app.rec.storageError ? '이 브라우저에 녹음을 저장할 수 없어요. 사생활 보호(시크릿) 창이면 일반 창으로 열어 주세요.' : ''),
    };
  }
}

export default function AppUpload(props) {
  const app = useAppData();
  const { caseId } = useIds();
  // 다 올린 줄을 서버와 맞춘다(웹에서 지운 회차는 빼고, 남은 줄은 지금 상태를 받는다). 처리 중이면 20초마다 다시 본다.
  const [statuses, setStatuses] = useState({});
  const doneIds = app.rec.items.filter((x) => x.status === 'done').map((x) => x.id).join(',');
  useEffect(() => {
    if (!app.userId) return undefined;
    let live = true;
    let timer = null;
    const tick = async () => {
      try {
        const res = await syncDoneWithServer(app.userId);
        if (!live) return;
        setStatuses(res.statuses);
        if (Object.values(res.statuses).some((st) => st === 'STT_PROCESSING' || st === 'AI_PROCESSING')) timer = window.setTimeout(tick, 20_000);
      } catch {
        // 연결이 없으면 다음에 열 때
      }
    };
    void tick();
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [app.userId, doneIds]);
  const v = useDC(Logic, { ...props, app, initCase: caseId, statuses });
  return <View v={v} />;
}
