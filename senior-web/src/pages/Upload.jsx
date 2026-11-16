// 녹취 · 자료 올리기 — 디자인 Upload.dc.html. 사례 고르기 → 회차 고르기(새 회차 · 기존 회차) → 음성 올리기 → 원문 변환(STT) 요청.
//  - 사례: 고령자 사례(subject_type SENIOR)만. ?case= 로 들어오면 그 사례를 미리 고른다(?session= 이면 그 회차도).
//  - 'n회차까지 진행': 사례마다 회차 목록 전체 수(meta.total). 회차 이름은 상담일 · 상담 유형.
//  - 업로드: (새 회차면 POST /cases/{id}/sessions) → POST /sessions/{id}/audio → POST /sessions/{id}/transcript(202).
//    변환은 서버에서 이어지고, 1단계 기록 확인 화면(Step1Record)이 끝날 때까지 기다린다.
//  - 문서 파일(PDF · HWPX · DOCX · TXT)은 고령자 화면에서 아직 받지 않는다(준비 중 안내).
//  - 녹음 동의 체크를 해야 올린다.
import { useState } from 'react';
import { useDC } from '../dc';
import DesignLogic from '../design/Upload.logic';
import { cases, sessions, transcript } from '@cw/api/endpoints';
import { CONSULTATION_TYPE_LABELS } from '@cw/api/types';
import { checkAudioFile, readAudioDuration } from '@cw/data/audioFile';
import { errorMessage } from '@cw/data/useRemote';
import { parseBackendTime } from '@cw/data/time';
import { mapLimited } from '@cw/data/mapLimited';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { href, useIds } from '../data/nav';
import { DASH } from '../data/format';
import View from './Upload.view';

const AUDIO_RE = /\.(mp3|m4a|wav|aac|ogg|mp4|flac|webm)$/i;

function md(value) {
  const d = value ? parseBackendTime(value) : null;
  return d ? `${d.getMonth() + 1}/${d.getDate()}` : DASH;
}

function sessionName(row) {
  const kind = row.consultation_type ? CONSULTATION_TYPE_LABELS[row.consultation_type] : row.title || '상담';
  return `${md(row.consulted_at || row.created_at)} ${kind}`;
}

class Logic extends DesignLogic {
  resetFlow() {
    super.resetFlow();
    setTimeout(() => this.setState({ raw: null, consent: false, err: '', busy: false, doneSession: null }), 0);
  }

  renderValsBase() {
    const base = super.renderValsBase();
    const s = this.state;
    const { list, counts, ses, cid, setCid, sid, setSid, query, setQuery, shell, presetCase } = this.props;
    const radio = (on) => ({ bd: on ? '#1F3A56' : '#D9E3EA', bg: on ? '#E8F4FC' : '#FFFFFF', dot: on ? '#1F3A56' : '#C5D4DE', fill: on ? '#1F3A56' : 'transparent' });

    // 1) 사례
    const items = list.data ? list.data.items : [];
    const countOf = (id) => (counts.data && counts.data[id] !== undefined ? counts.data[id] : null);
    const caseRows = items.map((c) => {
      const n = countOf(c.id);
      return {
        name: c.child_alias || DASH,
        meta: `${c.case_number || DASH} · ${n === null ? DASH : n === 0 ? '회차 없음' : `${n}회차까지 진행`}`,
        ...radio(c.id === cid),
        pick: () => { setCid(c.id); setSid(null); this.setState({ err: '' }); },
      };
    });
    if (!items.length) {
      caseRows.push({ name: list.loading ? '불러오는 중…' : list.error ? errorMessage(list.error, '사례를 불러오지 못했습니다.') : '고령자 사례가 없습니다', meta: '', ...radio(false), pick: () => {} });
    }
    const picked = items.find((c) => c.id === cid) || (presetCase.data && presetCase.data.id === cid ? presetCase.data : null);
    const caseName = picked ? `${picked.child_alias || DASH} · ${picked.case_number || DASH}` : DASH;

    // 2) 회차: 0 = 새 회차, 그 뒤는 최신 회차부터
    const rows = ses.data ? [...ses.data.items].sort((a, b) => b.session_number - a.session_number) : [];
    const last = rows.length ? rows[0].session_number : 0;
    const xs = [{ id: null, label: `새 회차 · ${last + 1}회차`, meta: '새로 등록' }].concat(
      rows.map((r) => ({ id: r.id, label: `${r.session_number}회차 · ${sessionName(r)}`, meta: r.status === 'CREATED' ? '녹취 아직 없음' : '녹취 있음' })),
    );
    // 고른 회차: 넘겨받은 회차 → 가장 최근 회차가 녹취 전이면 그 회차 → 새 회차
    let xSel = 0;
    if (sid && sid !== 'new') xSel = Math.max(0, xs.findIndex((x) => x.id === sid));
    else if (!sid && rows.length && rows[0].status === 'CREATED') xSel = 1;
    const sessionsVals = ses.loading && !rows.length
      ? [{ label: '불러오는 중…', meta: '', ...radio(false), pick: () => {} }]
      : xs.map((x, i) => ({ label: x.label, meta: x.meta, ...radio(i === xSel), pick: () => { setSid(x.id || 'new'); this.setState({ err: '' }); } }));
    const sesLabel = xSel === 0 ? `${last + 1}회차 (새 회차)` : xs[xSel].label.split(' · ')[0];

    // 3) 파일 · 올리기
    const pickFile = (e) => {
      base.pickFile(e);
      const t = e && e.target && e.target.files && e.target.files[0];
      if (t) this.setState({ raw: t, err: '' });
    };
    const upload = async () => {
      if (s.busy) return;
      const file = s.raw;
      if (!cid) return this.setState({ err: '어르신(사례)을 먼저 골라 주세요.' });
      if (!file || !s.file) return this.setState({ err: '올릴 파일을 골라 주세요.' });
      if (!(AUDIO_RE.test(file.name) || /^audio\//.test(file.type || ''))) return this.setState({ err: '문서 파일 올리기는 준비 중이에요. 지금은 음성 파일만 올릴 수 있어요.' });
      const problem = checkAudioFile(file);
      if (problem) return this.setState({ err: problem });
      if (!s.consent) return this.setState({ err: '녹음 동의를 확인한 뒤 올려 주세요.' });
      this.setState({ busy: true, err: '' });
      let target = xs[xSel].id;
      try {
        if (!target) {
          const made = await cases.createSession(cid, { consulted_at: new Date().toISOString() });
          target = made.id;
          setSid(target);
        }
        const durationMs = await readAudioDuration(file).catch(() => undefined);
        await sessions.uploadAudio(target, file, durationMs);
        await transcript.run(target);
        this.setState({ busy: false, confirm: true, doneSession: target });
      } catch (caught) {
        this.setState({ busy: false, err: errorMessage(caught, '올리지 못했습니다. 잠시 후 다시 시도해 주세요.') });
      }
    };

    const next = () => {
      if (s.step === 1 && !cid) return this.setState({ err: '어르신(사례)을 먼저 골라 주세요.' });
      if (s.step === 2 && ses.loading) return;
      this.setState({ err: '' });
      base.next();
    };

    return {
      ...base, ...shell,
      cases: caseRows, sessions: sessionsVals, caseName, sesLabel,
      pickFile, upload, next,
      prev: () => { this.setState({ err: '' }); base.prev(); },
      search: query, setSearch: (e) => setQuery(e.target.value),
      consent: !!s.consent, setConsent: (e) => this.setState({ consent: e.target.checked, err: '' }),
      uploadLabel: s.busy ? '올리는 중…' : '업로드',
      err: s.err || '', hasErr: !!s.err,
      step1Href: href('Step1Record', { caseId: cid, sessionId: s.doneSession }),
      clearFile: () => this.setState({ file: null, raw: null }),
    };
  }
}

export default function Upload(props) {
  const shell = useShell();
  const ids = useIds();
  const [cid, setCid] = useState(ids.caseId);
  const [sid, setSid] = useState(ids.sessionId);
  const [query, setQuery] = useState('');
  const list = useAsync(() => {
    if (!shell.ready) return null;
    return cases.list({ subject_type: 'SENIOR', page: 1, page_size: 100, search: query.trim() || undefined });
  }, [shell.ready, query]);
  // 사례마다 회차 수(목록 칸 'n회차까지 진행')
  const counts = useAsync(async () => {
    if (!list.data) return null;
    const out = {};
    await mapLimited(list.data.items, 4, async (c) => {
      try {
        const page = await cases.listSessions(c.id, { page: 1, page_size: 1 });
        out[c.id] = page.meta.total;
      } catch (e) {
        out[c.id] = null;
      }
    });
    return out;
  }, [list.data]);
  // ?case= 로 들어왔는데 검색 결과에 없을 때도 이름을 보이려고
  const presetCase = useAsync(() => (shell.ready && ids.caseId ? cases.get(ids.caseId) : null), [shell.ready, ids.caseId]);
  const ses = useAsync(() => (shell.ready && cid ? cases.listSessions(cid, { page: 1, page_size: 100 }) : null), [shell.ready, cid]);
  const v = useDC(Logic, { ...props, shell, list, counts, ses, cid, setCid, sid, setSid, query, setQuery, presetCase });
  return <View v={v} />;
}
