// 사례 상세 · 문서함 — 디자인 CaseDocs.dc.html. 주소 ?case=<사례 id>.
//  - '녹취 · 일지 · 외부 문서' 표: 이 사례 회차마다 서버에 있는 것만 줄로 보인다.
//      녹음 파일(GET /sessions/{id}/audio) · 녹취 원문(STT, 회차 상세의 원문 판 · 검수 여부) · 상담 요약(승인 여부, summary)
//      · 회차 문서(documents.list) · 올린 상담 기록 문서(source-document → '외부 문서').
//    '브리핑' 은 사례의 방문 전 브리핑(senior-brief)이 있으면 다음 회차 줄 하나(누르면 탭1 브리핑).
//  - '기관 서식' 표: 서식 이름 · 작성 시점은 디자인(기관 양식) 그대로, 사례별 작성 기록은 서버에 없어 최근 작성 '—' · 상태 '준비 중'.
//    '열기' 는 빈 양식을 읽기 전용으로 보인다(디자인 예시 기록 값은 넣지 않는다). 종결보고서 등 아동 전용 서식 기록은 쓰지 않는다.
//  - 이름은 별칭(실명 열람 기록은 탭1 에서만 남긴다). 고령자에는 위기도 판정이 없어 칩은 '—'.
//  - 녹음하기 · 자료 올리기는 Upload 화면으로(이 사례를 싣고).
import { useDC } from '../dc';
import DesignLogic from '../design/CaseDocs.logic';
import { cases, sessions as sessionsApi, documents, sourceDocuments } from '@cw/api/endpoints';
import { senior } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { useIds, href } from '../data/nav';
import { DASH, md } from '../data/format';
import { caseLinks, subLine, visitWhen } from './CaseInfo.parts';
import View from './CaseDocs.view';

const soft = (p) => p.catch(() => null);
const DOC_STATUS = { DRAFT: ['작성 중', 'chip c-check'], APPROVED: ['확정', 'chip c-ok'] };
// 기관 서식 줄의 '수정' 이 갈 화면(디자인 링크 그대로, 사례 id 를 싣는다).
const FORM_PAGE = { f4: 'CaseIntake', s7: 'Step3Summary', f29: 'Followup' };

class Logic extends DesignLogic {
  // 빈 양식으로 보인다 — 디자인의 예시 기록 값(이름 · 날짜 · 응답)은 쓰지 않는다.
  cdVals() {
    return {};
  }

  renderValsBase() {
    const base = super.renderValsBase();
    const s = this.state;
    const { data, caseId, shell, loadErr } = this.props;
    const d = data || {};
    const c = d.c;
    const list = d.sessions || [];
    const latest = list[0] || null;
    const links = caseLinks(caseId, latest && latest.id);
    const name = (c && c.child_alias) || DASH;
    const no = (c && c.case_number) || DASH;
    const nv = d.brief && d.brief.next_visit;
    const ids = (x) => ({ caseId, sessionId: x.id });

    // 회차마다 줄 만들기(최신 회차부터)
    const all = [];
    list.forEach((x) => {
      const ses = `${x.session_number}회차`;
      const info = (d.perSession || {})[x.id] || {};
      const det = info.detail;
      if (info.audio) {
        all.push({ name: info.audio.original_filename || '녹음 파일', kind: '녹취', ses, date: `${md(info.audio.created_at)} 업로드`,
          st: '올림', stCls: 'chip c-ok', href: href('SessionDetail', ids(x)), go: '열기', f: 'rec' });
      }
      if (det && det.has_transcript) {
        const ok = det.transcript_confirmed;
        all.push({ name: `${ses} 기록 확인본${det.transcript_version ? ` (v${det.transcript_version})` : ''}`, kind: '녹취', ses,
          date: x.stt_completed_at ? md(x.stt_completed_at) : DASH, st: ok ? '검수 완료' : '검수 대기', stCls: ok ? 'chip c-ok' : 'chip c-check',
          href: href('Step1Record', ids(x)), go: ok ? '열기' : '기록 확인', f: 'rec' });
      }
      if (det && det.has_summary) {
        const ok = det.summary_approved;
        all.push({ name: `${ses} 상담일지`, kind: '상담 일지', ses, date: md(x.approved_at || x.ai_completed_at || x.updated_at),
          st: ok ? '확정' : '검토 대기', stCls: ok ? 'chip c-ok' : 'chip c-check',
          href: href(ok ? 'SessionDetail' : 'Step3Summary', ids(x)), go: '열기', f: 'note' });
      }
      (info.docs || []).forEach((doc) => {
        const st = DOC_STATUS[doc.status] || [DASH, 'chip c-normal'];
        all.push({ name: doc.title, kind: '상담 일지', ses, date: md(doc.approved_at || doc.updated_at), st: st[0], stCls: st[1],
          href: href('SessionDetail', ids(x)), go: '열기', f: 'note' });
      });
      if (info.source) {
        all.push({ name: info.source.filename, kind: '외부 문서', ses, date: md(info.source.created_at), st: '보관', stCls: 'chip c-normal',
          href: href('Step1Record', ids(x)), go: '열기', f: 'ext' });
      }
    });
    if (d.brief) {
      const nextNo = (latest ? latest.session_number : 0) + 1;
      all.unshift({ name: `${nextNo}회차 상담 전 브리핑`, kind: '브리핑', ses: `${nextNo}회차`, date: md(d.brief.generated_at),
        st: '준비됨', stCls: 'chip c-sky', href: href('CaseInfo', { caseId, sec: 'brief' }), go: '열기', f: 'brief' });
    }
    const f = s.f || 'all';
    const rows = all.filter((r) => f === 'all' || r.f === f);
    if (!rows.length) {
      rows.push({ name: loadErr || (this.props.loading ? '불러오는 중…' : '아직 문서가 없어요'), kind: DASH, ses: DASH, date: DASH, st: DASH, stCls: 'chip c-normal', href: undefined, go: '' });
    }

    // 기관 서식: 이름 · 번호 · 작성 시점만 디자인 그대로, 기록은 준비 중.
    const forms = (base.forms || []).map((r) => ({ ...r, date: DASH, st: '준비 중', stCls: 'chip c-normal' }));
    const cur = base.cvOpen;
    const cvKey = s.cv !== undefined && s.cv !== null ? ['f4', 'f6', 's3', 's4', 's5', 's6', 's7', 'f29', 'f27', 'r3', 'r1'][s.cv] : null;
    const cvPage = cvKey ? FORM_PAGE[cvKey] || 'CaseForm' : 'CaseForm';
    const cvSession = cvPage === 'Step3Summary' && latest ? latest.id : undefined;

    return {
      ...base,
      ...shell,
      ...links,
      docsHref: href('CaseDocs', { caseId }),
      crumb: `${name} ${no}`,
      name,
      sub: subLine(c, d.profile),
      riskLabel: `위기도 ${DASH}`,
      riskCls: 'chip c-lo',
      headNote: `${no} · 다음 상담 ${nv ? visitWhen(nv.date, nv.time) : DASH}`,
      caseLabel: `${name} · ${no}`,
      rows,
      forms,
      cvSt: cur ? '준비 중' : '',
      cvStCls: 'chip c-normal',
      cvMeta: cur ? '빈 양식 · 이 대상자의 작성 기록은 준비 중' : '',
      cvHref: href(cvPage, { caseId, sessionId: cvSession }),
    };
  }

  renderVals() {
    const v = super.renderVals();
    return { ...v, recOpen: v.goUpload, navLinkCnt: '', navFollowCnt: '' };
  }
}

export default function CaseDocs(props) {
  const shell = useShell();
  const { caseId } = useIds();
  const main = useAsync(async () => {
    if (!shell.ready || !caseId) return null;
    const [c, profile, page, brief] = await Promise.all([
      cases.get(caseId),
      soft(senior.profile(caseId)),
      soft(cases.listSessions(caseId, { page_size: 100 })),
      soft(senior.brief(caseId)),
    ]);
    const list = page ? [...page.items].sort((a, b) => b.session_number - a.session_number) : [];
    const perSession = {};
    // 회차가 많을 수 있어 네 회차씩 부른다.
    for (let i = 0; i < list.length; i += 4) {
      await Promise.all(
        list.slice(i, i + 4).map(async (x) => {
          const [detail, docs] = await Promise.all([soft(sessionsApi.get(x.id)), soft(documents.list(x.id))]);
          // 녹음은 있는 회차만, 상담 기록 문서는 녹음이 아닌 회차(문서로 올린 회차)만 부른다(없는 것을 불러 404 를 내지 않게).
          const [audio, source] = await Promise.all([
            detail && detail.has_audio ? soft(sessionsApi.getAudio(x.id)) : null,
            x.source && x.source !== 'AUDIO' ? soft(sourceDocuments.get(x.id)) : null,
          ]);
          perSession[x.id] = { detail, docs: docs || [], audio, source };
        }),
      );
    }
    return { c, profile, sessions: list, brief, perSession };
  }, [shell.ready, caseId]);

  let loadErr = '';
  if (!caseId) loadErr = '대상자를 고르지 않았어요. 대상자 목록에서 다시 들어와 주세요.';
  else if (main.error) loadErr = main.error.message || '문서를 불러오지 못했어요.';
  const v = useDC(Logic, { ...props, shell, caseId, data: main.data, loading: main.loading, loadErr });
  return <View v={v} />;
}
