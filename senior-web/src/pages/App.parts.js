// 상담사 앱(폰) 화면 9개(AppHome · AppCases · AppNext · AppUpload · AppMemo · AppSchedule · AppRecord · AppHistory · AppSettings)가
// 같이 쓰는 것. 공용 파일(src/data)은 고치지 않기로 해 여기 둔다(.parts.js 라 화면 경로로 등록되지 않는다).
//  - 대상자: 내 진행 중 고령자 사례(GET /cases?subject_type=SENIOR&status=ACTIVE). 이름은 별칭(실명 열람 기록은 웹 탭1 에서만 남긴다).
//  - 올리기 대기열: counselor-web 의 폰 녹음 대기열(appRecordings · useAppRecordings) 그대로 — 이 브라우저(IndexedDB)에 먼저 두고
//    회차 만들기 → 음성 올리기 → 원문 변환 요청. 실패한 줄은 '다시 올리기'.
//  - 알림(종): 업로드 실패 줄 + 오늘 남은 상담(서버 일정) + 오늘 남은 첫 상담의 '다음 상담 준비'.
//    디자인 로직의 예시 대기열 · 예시 알림은 쓰지 않는다(qRead · commonVals 를 덮는다).
import { cases } from '@cw/api/endpoints';
import { SCHEDULE_CONSULT_LABELS, SCHEDULE_CATEGORY_LABELS, CONSULTATION_TYPE_LABELS } from '@cw/api/types';
import { useAppRecordings } from '@cw/data/useAppRecordings';
import { retryRecording, uploadAsNewSession } from '@cw/data/appRecordings';
import { useAppSchedule, ymd as dayKey, addDays, mondayOf, parseYmd } from '@cw/data/useAppSchedule';
import { parseBackendTime } from '@cw/data/time';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { href } from '../data/nav';
import { DASH, age, genderLabel } from '../data/format';

export { dayKey, addDays, mondayOf, parseYmd };

const W = ['일', '월', '화', '수', '목', '금', '토'];
const pad = (n) => String(n).padStart(2, '0');

/** 대상자 이름(별칭). */
export const nameOf = (c) => (c && c.child_alias) || DASH;

/** '만 82세 · 여' (+ 가구형태가 있으면 ' · 독거'). */
export function ageLine(c, living) {
  if (!c) return DASH;
  const a = age(c.child_birth_year);
  return [a !== null ? `만 ${a}세` : DASH, genderLabel(c.child_gender), living || null].filter(Boolean).join(' · ');
}

/** 서버 시각(UTC, 시간대 없을 수 있음) → ms. */
export function msOf(iso) {
  const d = iso ? parseBackendTime(iso) : null;
  return d ? d.getTime() : Date.now();
}

/** '방금' · '오늘 15:20' · '어제 18:02' · '10/27 09:40'. */
export function whenText(ms) {
  const d = new Date(ms);
  const today = new Date();
  const y = new Date(today);
  y.setDate(today.getDate() - 1);
  const t = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  if (d.toDateString() === today.toDateString()) return Date.now() - ms < 60_000 ? '방금' : `오늘 ${t}`;
  if (d.toDateString() === y.toDateString()) return `어제 ${t}`;
  return `${d.getMonth() + 1}/${d.getDate()} ${t}`;
}

export function sizeText(bytes) {
  return bytes > 1048576 ? `${(bytes / 1048576).toFixed(1)}MB` : `${Math.max(1, Math.round((bytes || 0) / 1024))}KB`;
}

export const consultLabel = (t) => (t && SCHEDULE_CONSULT_LABELS[t]) || '상담';
export const categoryLabel = (t) => (t && SCHEDULE_CATEGORY_LABELS[t]) || '일정';
export const sessionKind = (t) => (t && CONSULTATION_TYPE_LABELS[t]) || DASH;

/** 일정 한 줄 → '11/24(화) 14:00 · 방문상담'. */
export function consultWhen(e) {
  const d = parseYmd(e.date);
  return `${d.getMonth() + 1}/${d.getDate()}(${W[d.getDay()]})${e.time ? ` ${e.time}` : ''} · ${consultLabel(e.consult_type)}`;
}

/** 일정 날짜 → '오늘' · '내일' · '11/24(화)'. */
export function dayWord(date) {
  const d = parseYmd(date);
  const t0 = parseYmd(dayKey(new Date()));
  const diff = Math.round((d - t0) / 86400000);
  if (diff === 0) return '오늘';
  if (diff === 1) return '내일';
  return `${d.getMonth() + 1}/${d.getDate()}(${W[d.getDay()]})`;
}

const nowKey = () => {
  const n = new Date();
  return `${dayKey(n)} ${pad(n.getHours())}:${pad(n.getMinutes())}`;
};
/** 지금 뒤의 상담인가(종일이면 그날 끝까지). */
export const upcoming = (e) => `${e.date} ${e.time || '23:59'}` >= nowKey();

/** 폰 대기열 줄 → 디자인 대기열 줄 모양. */
function qRow(x) {
  return {
    id: x.id,
    name: x.fileName,
    kind: '녹음',
    who: `${x.childLabel} · ${x.sessionNumber ? `${x.sessionNumber}회차` : '새 회차'}`,
    size: sizeText(x.size),
    status: x.status === 'wait' ? 'run' : x.status,
    err: x.error || '',
    t: whenText(x.status === 'done' ? x.updatedAt : x.createdAt),
    needNewSession: !!x.needNewSession,
  };
}

/**
 * 모든 앱 화면 공통: 로그인 확인(useShell) · 내 대상자 · 폰 대기열 · 오늘 일정.
 * 반환값을 화면 Logic 의 props.app 으로 넘긴다.
 */
export function useAppData() {
  const shell = useShell();
  const me = shell.session.me;
  const userId = shell.ready && me ? me.id : null;
  const rec = useAppRecordings(userId);
  const today = dayKey(new Date());
  const todayEv = useAppSchedule(!!userId, today, today);
  const list = useAsync(
    () => (userId ? cases.list({ subject_type: 'SENIOR', status: 'ACTIVE', page_size: 100 }) : null),
    [userId],
  );
  const elders = list.data ? list.data.items : [];
  return {
    shell,
    me,
    userId,
    rec,
    todayEv,
    elders,
    eldersLoading: !userId || list.loading,
    eldersErr: list.error ? list.error.message || '대상자 목록을 불러오지 못했어요.' : '',
  };
}

/** 대상자 고르기 칸 목록({v: 사례 ID, label: 이름}). */
export function elderOpts(app, loadingLabel = '불러오는 중') {
  if (app.elders.length) return app.elders.map((c) => ({ v: c.id, label: nameOf(c) }));
  return [{ v: '', label: app.eldersLoading ? loadingLabel : '담당 대상자 없음' }];
}

/**
 * 디자인 로직(DesignLogic)에 서버 값을 넣는 공통 덮개. 예시 대기열 · 예시 이름 · 예시 알림 대신 실제 값을 쓴다.
 * 화면 Logic 은 `class Logic extends withApp(DesignLogic)` 으로 쓰고, props.app 에 useAppData() 를 넘긴다.
 */
export function withApp(Base) {
  return class extends Base {
    qItems() {
      const app = this.props.app;
      return app ? app.rec.items : [];
    }

    qRead() {
      return this.qItems().map(qRow);
    }

    // 폰 대기열은 appRecordings 가 쓴다(디자인의 localStorage 대기열 · 예시 줄은 쓰지 않는다).
    qWrite() {}

    qAdd() {
      return '';
    }

    qRetry(id) {
      const it = this.qItems().find((x) => x.id === id);
      if (!it) return;
      void (it.needNewSession ? uploadAsNewSession(id) : retryRecording(id));
    }

    elders() {
      const app = this.props.app;
      return app ? app.elders.map(nameOf) : [];
    }

    commonVals(cur) {
      const c = super.commonVals(cur);
      const app = this.props.app;
      const fails = this.qRead().filter((x) => x.status === 'fail');
      const left = app ? app.todayEv.items.filter((e) => e.kind === 'CONSULT' && upcoming(e)) : [];
      const first = left.find((e) => e.case_id);
      const notes = fails.map((x) => ({
        red: 'red', title: `업로드 실패 · ${x.kind}`, sub: `${x.name} · ${x.t}`, desc: x.err || '',
        hasAct: true, act: x.needNewSession ? '새 회차로 올리기' : '다시 올리기', go: () => this.qRetry(x.id),
        hasLink: false, href: '', linkLabel: '', nav: () => {},
      }));
      if (first) {
        notes.push({
          red: '', title: '다음 상담 준비를 볼 수 있어요', sub: `오늘 ${first.time || '종일'} · ${first.child_alias || DASH} · ${consultLabel(first.consult_type)}`,
          desc: '', hasAct: false, act: '', go: () => {}, hasLink: true, href: href('AppNext', { caseId: first.case_id }), linkLabel: '다음 상담 준비 보기',
          nav: () => this.stSet('ispot-app-from', `#/${{ home: 'AppHome', cases: 'AppCases', cal: 'AppSchedule', memo: 'AppMemo', up: 'AppUpload', rec: 'AppRecord', set: 'AppSettings' }[cur] || 'AppHome'}`),
        });
      }
      if (left.length) {
        notes.push({
          red: '', title: `오늘 남은 상담 ${left.length}건`, sub: left.map((e) => `${e.time || '종일'} ${e.child_alias || DASH}`).join(' · '),
          desc: '', hasAct: false, act: '', go: () => {}, hasLink: true, href: '#/AppSchedule', linkLabel: '일정 보기', nav: () => {},
        });
      }
      return {
        ...c,
        notes,
        ntCount: String(notes.length),
        ntHas: notes.length > 0,
        failN: fails.length,
        hasFail: fails.length > 0,
        failText: `업로드 실패 ${fails.length}건 · 다시 올려 주세요`,
      };
    }
  };
}
