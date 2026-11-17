// LawGuide 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/LawGuide.jsx)이 이어받아 데이터만 바꾼다.
/* eslint-disable */
import { DCLogic } from '../dc';

export default class DesignLogic extends DCLogic {
themeRead() {
  const K = 'ispot-theme'; let v = null;
  try { v = window.localStorage.getItem(K); } catch (e) {}
  if (!v) { try { v = window.sessionStorage.getItem(K); } catch (e) {} }
  if (!v) { try { v = window.top.__ispotTheme; } catch (e) {} }
  if (!v) { v = window.__ispotTheme; }
  return v === 'dark';
}
themeWrite(dark) {
  const K = 'ispot-theme'; const v = dark ? 'dark' : 'light';
  try { window.localStorage.setItem(K, v); } catch (e) {}
  try { window.sessionStorage.setItem(K, v); } catch (e) {}
  try { window.top.__ispotTheme = v; } catch (e) {}
  window.__ispotTheme = v;
}
jobRead() { let v = null; try { v = window.localStorage.getItem('ispot-job'); } catch (e) {} if (!v) { try { v = window.sessionStorage.getItem('ispot-job'); } catch (e) {} } if (!v) { try { v = window.top.__ispotJob; } catch (e) {} } if (!v) v = window.__ispotJob; try { return v ? JSON.parse(v) : null; } catch (e) { return null; } }
jobPhase() { const j = this.jobRead(); if (!j || !j.t) return ''; const el = Date.now() - j.t; return el < 8000 ? 'run' : el < 11000 ? 'done' : el < 11500 ? 'out' : ''; }
jobWrite(v) { try { window.localStorage.setItem('ispot-job', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-job', v); } catch (e) {} try { window.top.__ispotJob = v; } catch (e) {} window.__ispotJob = v; }
componentDidMount() {
  this._ntRaw = this.ntGet('ispot-intake') + this.ntGet('ispot-noti-read'); this._ntT = setInterval(() => { const r = this.ntGet('ispot-intake') + this.ntGet('ispot-noti-read'); if (r !== this._ntRaw) { this._ntRaw = r; this.setState({ __ntTick: Date.now() }); } }, 700);
  this._ntDoc = (e) => { if (this.state && this.state.__ntOpen && !(e.target && e.target.closest && e.target.closest('.nt-wrap'))) this.setState({ __ntOpen: false }); }; try { document.addEventListener('mousedown', this._ntDoc); } catch (e) {}
  this._thmT = setInterval(() => { if (this.jobPhase() !== this._jobPh || this.themeRead() !== this._thmShown) this.setState({ __thmTick: Date.now() }); }, 300);
  if (this.componentDidMountBase) this.componentDidMountBase();
}
componentWillUnmount() {
  clearInterval(this._ntT); try { document.removeEventListener('mousedown', this._ntDoc); } catch (e) {}
  clearInterval(this._thmT);
  if (this.componentWillUnmountBase) this.componentWillUnmountBase();
}
ntGet(k) { let v = null; try { v = window.localStorage.getItem(k); } catch (e) {} if (!v) { try { v = window.sessionStorage.getItem(k); } catch (e) {} } if (!v) { try { v = (window.top.__ispotSt || {})[k]; } catch (e) {} } if (!v) v = (window.__ispotSt || {})[k]; return v || ''; }
ntSet(k, v) { try { window.localStorage.setItem(k, v); } catch (e) {} try { window.sessionStorage.setItem(k, v); } catch (e) {} try { window.top.__ispotSt = window.top.__ispotSt || {}; window.top.__ispotSt[k] = v; } catch (e) {} window.__ispotSt = window.__ispotSt || {}; window.__ispotSt[k] = v; }
ntRecs() { try { const a = JSON.parse(this.ntGet('ispot-intake') || '[]'); return Array.isArray(a) ? a : []; } catch (e) { return []; } }
ntSave(a) { this.ntSet('ispot-intake', JSON.stringify(a)); }
ntTasks() { return [[3, '어르신 첫 안부 전화'], [7, '초기상담 · 동의 확인'], [30, '상담 계획 수립']]; }
ntReadIds() { try { return JSON.parse(this.ntGet('ispot-noti-read') || '[]'); } catch (e) { return []; } }
ntGo0() { let g = null; try { g = JSON.parse(this.ntGet('ispot-sched-go') || 'null'); } catch (e) {} if (!g || !g.t || Date.now() - g.t > 15000) return null; this.ntSet('ispot-sched-go', ''); return g; }
ntVals() {
  const recs = this.ntRecs(); const read = this.ntReadIds(); const days = ['일', '월', '화', '수', '목', '금', '토'];
  const t0 = new Date(); t0.setHours(0, 0, 0, 0);
  const items = [];
  recs.forEach((r) => this.ntTasks().forEach(([n, task]) => { if ((r.done || {})[n]) return; const due = new Date(r.y, r.m, r.d + n); const diff = Math.round((due - t0) / 86400000); const id = r.id + '-' + n;
    items.push({ id, due, diff, unread: read.indexOf(id) < 0, title: r.child + ' · ' + task, sub: '접수 후 ' + n + '일 이내 · ' + (due.getMonth() + 1) + '/' + due.getDate() + '(' + days[due.getDay()] + ')까지', y: due.getFullYear(), m: due.getMonth(), d: due.getDate() }); }));
  items.sort((a, b) => a.due - b.due);
  const unread = items.filter((x) => x.unread).length; const open = !!(this.state && this.state.__ntOpen);
  const markRead = (ids) => { const cur = this.ntReadIds(); this.ntSet('ispot-noti-read', JSON.stringify([...cur, ...ids.filter((i) => cur.indexOf(i) < 0)])); };
  return {
    ntOpen: open, ntExp: open ? 'true' : 'false', ntHasBadge: unread > 0, ntBadge: unread > 9 ? '9+' : String(unread),
    ntLabel: unread > 0 ? '알림 ' + unread + '건 읽지 않음' : '알림',
    ntSub: items.length ? '처리 기한 ' + items.length + '건' : '', ntEmpty: items.length === 0,
    ntToggle: () => this.setState({ __ntOpen: !open }),
    ntReadAll: () => { markRead(items.map((x) => x.id)); this.setState({ __ntTick: Date.now() }); },
    ntItems: items.map((x) => ({ title: x.title, sub: x.sub, cls: x.unread ? 'unread' : 'read',
      dd: x.diff < 0 ? '기한 지남' : x.diff === 0 ? '오늘 마감' : 'D-' + x.diff, ddCls: x.diff <= 0 ? 'urgent' : x.diff <= 2 ? 'soon' : '',
      go: (e) => { markRead([x.id]); this.ntSet('ispot-sched-go', JSON.stringify({ y: x.y, m: x.m, d: x.d, t: Date.now() })); this.setState({ __ntOpen: false, __ntTick: Date.now() }); if (this.schedGo) { if (e && e.preventDefault) e.preventDefault(); this.ntSet('ispot-sched-go', ''); this.schedGo(x.y, x.m, x.d); } } }))
  };
}
renderVals() {
  const v = this.renderValsBase() || {};
  const dark = this.themeRead(); this._thmShown = dark; const jp = this.jobPhase(); this._jobPh = jp; const jj = jp ? (this.jobRead() || {}) : {};
  return Object.assign({}, v, this.ntVals(), { jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), markBack: () => { const v = '#/LawGuide'; try { window.localStorage.setItem('ispot-back', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-back', v); } catch (e) {} try { window.top.__ispotBack = v; } catch (e) {} window.__ispotBack = v; }, themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

constructor(props) { super(props); this.state = { open: { report: true }, msgs: [{ role: 'bot', text: '안녕하세요. 노인복지법 · 돌봄통합지원법 · 자살예방법 등 시니어 상담 관련 법령과 2026년 노인보건복지사업안내 등 지침을 바탕으로 답해 드려요.\n아래 예시를 누르거나 직접 질문해 보세요.' }], draft: '', typing: false }; }
componentDidMountBase() {}
componentWillUnmountBase() { clearTimeout(this._tyT); }
componentDidUpdate() { const id = this._scrollTo; if (id) { this._scrollTo = null; setTimeout(() => { try { const el = document.getElementById(id); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' }); } catch (e) {} }, 60); } if (this._msgScroll) { this._msgScroll = false; setTimeout(() => { try { const box = document.getElementById('lg-msgs'); if (box) box.scrollTop = box.scrollHeight; } catch (e) {} }, 30); } }
renderValsBase() {
  const s = this.state;
  const LAW = { ow: ['노인복지법', 'https://www.law.go.kr/법령/노인복지법'], ci: ['돌봄통합지원법', 'https://www.law.go.kr/법령/의료ㆍ요양등지역돌봄의통합지원에관한법률'], mh: ['정신건강복지법', 'https://www.law.go.kr/법령/정신건강증진및정신질환자복지서비스지원에관한법률'], sp: ['자살예방법', 'https://www.law.go.kr/법령/자살예방및생명존중문화조성을위한법률'], dm: ['치매관리법', 'https://www.law.go.kr/법령/치매관리법'], ld: ['고독사예방법', 'https://www.law.go.kr/법령/고독사예방및관리에관한법률'], ltc: ['노인장기요양보험법', 'https://www.law.go.kr/법령/노인장기요양보험법'], pr: ['개인정보 보호법', 'https://www.law.go.kr/법령/개인정보보호법'], sw: ['사회복지사업법', 'https://www.law.go.kr/법령/사회복지사업법'], ss: ['사회보장급여법', 'https://www.law.go.kr/법령/사회보장급여의이용ㆍ제공및수급권자발굴에관한법률'] };
  const REFS = [
    { id: 'intake', step: '접수', title: '상담 접수 · 의뢰 경로 확인', pages: '기관 시니어 상담 매뉴얼', sum: '누가 왜 의뢰했는지, 어르신 본인이 상담을 알고 원하시는지 먼저 확인',
      items: ['의뢰 경로 확인: 본인 · 가족 · 행정복지센터 · 맞춤돌봄 수행기관(생활지원사) · 의료기관 · 치매안심센터 등',
        '주호소와 의뢰 사유는 의뢰인의 표현 그대로 기록하고, 상담사의 추측은 구분해 적기',
        '어르신 본인이 의뢰 사실을 알고 계신지, 상담을 원하시는지 확인(본인 의사가 우선)',
        '접수 단계에서 정서 · 위기 신호를 먼저 확인: 죽음 · 자살 언급, 며칠째 식사 거름, 연락 두절, 낙상 · 건강 급변',
        '위기 신호가 있으면 일반 절차보다 위기 개입을 먼저(109 · 정신건강복지센터 · 119)',
        '이미 이용 중인 서비스(노인맞춤돌봄서비스 · 장기요양 · 방문건강관리)를 확인해 중복 개입을 피하기'],
      laws: [['pr', '제15조 (개인정보의 수집 · 이용)'], ['ss', '· 지원대상자 발굴 · 연계']] },
    { id: 'consent', step: '초기상담 · 동의', title: '상담 동의 · 가족 공유 범위', pages: 'S-01 초기상담지(시니어용)', sum: '판단능력 있는 성인으로 존중하고, 동의 범위 안에서만 가족과 공유',
      items: ['상담 목적 · 방법 · 기록 보관 · 비밀보장과 그 예외(생명 위험 등)를 천천히, 쉬운 말로 설명',
        '본인 동의가 원칙. 대리 동의를 받는 경우 사유와 관계를 S-01에 기록',
        '가족 정보 공유 동의 범위를 따로 확인: 공유 동의 / 일부 동의 / 미동의 — 배지로 표시하고 범위 밖 내용은 가족에게 전하지 않음',
        '녹음은 별도 동의. 동의하지 않으셔도 상담에 불이익이 없음을 안내',
        '질환 · 복용 약 등 건강 정보는 민감정보이므로 별도 동의를 받아 처리',
        '어르신이 원하지 않으시면 언제든 상담을 멈출 수 있음을 안내(자기결정권 존중)'],
      laws: [['pr', '제23조 (민감정보의 처리 제한)'], ['pr', '제17조 (개인정보의 제공)']] },
    { id: 'comm', step: '초기상담 · 동의', title: '의사소통 고려 · 존중 언어', pages: '기관 시니어 상담 매뉴얼', sum: '청력 · 시력 · 말 속도에 맞추고, 존댓말과 선호 호칭 사용',
      items: ['청력(보청기 사용) · 시력을 먼저 확인하고, 조용한 곳에서 마주 앉아 천천히, 또박또박 말씀드리기',
        '안내문은 큰 글씨로 드리고, 중요한 내용은 한 번 더 말씀드린 뒤 이해하셨는지 확인',
        '선호 호칭을 여쭙고 기록(예: "김순자 님", "선생님"). 반말 · 유아어 · 낮잡는 말은 쓰지 않음',
        '사투리와 말 속도를 존중하고 말씀을 끊지 않기. 생각하시는 동안의 침묵도 기다리기',
        'AI 요약과 기록 문장도 같은 원칙(존댓말, 낙인어 금지)을 따름',
        '동의능력이 염려되면 상담사가 판단하지 않고, 관찰 내용을 기록한 뒤 슈퍼바이저와 협의'],
      laws: [] },
    { id: 'assess', step: '사정', title: '욕구 · 자원 사정과 선별 척도', pages: 'S-02 ~ S-06 기관 서식', sum: '영역별 욕구와 강점을 함께 보고, 척도는 선별용으로만 사용',
      items: ['S-02 욕구 · 자원 사정: 정서 · 건강 · 인지 · 사회관계 · 가족 · 경제 · 주거 · 여가 영역별 욕구와 강점 · 자원',
        'S-03 단축형 노인우울척도(SGDS-K, 15문항): 선별 결과이며 진단이 아님 · 기준 이상이면 정신건강복지센터 연계 검토',
        'S-04 자살위험 선별: 죽음 · 자살 생각, 계획, 수단 접근, 과거 시도, 최근 상실, 보호요인 확인',
        'S-05 외로움 · 사회적 고립: 교류 빈도, 연락할 사람 유무, 외로움 체감',
        'S-06 인지 변화 관찰: 같은 질문 반복, 날짜 혼동, 약 복용 잊음, 길 잃음 등. 상담사는 진단하지 않으며 변화가 보이면 치매안심센터 선별검사 연계',
        '가족 지지 · 관계 척도로 주 돌봄자의 부양 부담도 살피되, 내담자는 어르신 본인임을 유지'],
      laws: [['dm', '· 치매안심센터 선별검사'], ['mh', '· 정신건강복지센터 연계']] },
    { id: 'plan', step: '계획', title: '상담 목표 · 계획 수립', pages: '기관 시니어 상담 매뉴얼', sum: '어르신이 바라시는 일상에서 출발해 작고 구체적인 목표로',
      items: ['어르신이 원하시는 변화를 어르신의 말씀으로 목표에 담기(예: "다시 복지관에 나가고 싶어요")',
        '위기도(일반 · 관심 · 집중 · 위기)에 따라 상담 주기와 안부 확인 빈도를 정함',
        '상담 영역별(정서 · 우울 / 상실 · 애도 / 고립 · 외로움 / 건강 · 인지 / 가족관계 / 경제 · 주거 / 생활 적응 · 여가) 개입 내용 정리',
        '연계가 필요한 자원과 담당 기관을 함께 적고, 연계 전에 어르신 동의를 받기',
        '가족과 함께할 부분(돌봄자 교육 · 가족 상담)은 공유 동의 범위 안에서 계획'],
      laws: [] },
    { id: 'link', step: '개입 · 연계', title: '지역 돌봄 자원 연계', pages: '2026년 노인보건복지사업안내 · 노인맞춤돌봄서비스 사업안내', sum: '필요한 서비스로 이어 드리고, 연계 후에도 안부를 확인',
      items: ['노인맞춤돌봄서비스: 안부 확인 · 생활지원 · 사회참여 지원(수행기관 생활지원사와 협력)',
        '통합돌봄 창구(읍 · 면 · 동 행정복지센터): 의료 · 요양 · 돌봄 통합지원 상담과 신청',
        '방문건강관리(보건소), 치매안심센터(선별검사 · 쉼터 · 가족 지원), 정신건강복지센터(우울 · 자살 위험)',
        '일상생활에 도움이 많이 필요하시면 장기요양 등급 신청 안내(국민건강보험공단)',
        '노인복지관 · 경로당 프로그램으로 사회참여와 여가 연계',
        '경제적 어려움은 행정복지센터의 위기가구 지원 · 기초연금 · 기초생활보장 상담으로 연계',
        '연계 기관에 전하는 정보는 어르신 동의 범위 안에서만'],
      laws: [['ci', '· 통합지원 신청 · 연계'], ['ow', '· 노인맞춤돌봄서비스 근거']] },
    { id: 'crisis', step: '개입 · 연계', title: '자살 위험 · 위기 개입', pages: '정신건강사업안내 · 보고듣고말하기(노인용)', sum: '위기 신호는 다른 업무보다 먼저, 혼자 판단하지 않기',
      items: ['고령층은 자살 위험이 높으므로 우울감 · 상실 · 고립 신호가 보이면 자살 생각을 직접, 차분하게 여쭙기',
        '보기: 죽음 · 이별을 암시하는 말씀, 물건 정리, 식사 · 수면의 급격한 변화, 약을 모아 두심 등',
        '듣기: 판단하거나 설득하지 않고 끝까지 들으며 마음을 인정해 드리기',
        '말하기: 혼자 계시지 않도록 109(자살예방상담) · 정신건강복지센터로 연결, 급박하면 119 · 112 요청',
        '위험 수단(모아 둔 약 등)은 동의를 구해 함께 정리하고, 생명이 위험할 때는 비밀보장의 예외로 가족 · 생활지원사와 안전 계획 공유',
        '위기 개입 후 24시간 안에 안부 확인, 슈퍼바이저 보고와 S-04 · S-07 기록'],
      laws: [['sp', '· 자살위험자 지원 · 연계'], ['mh', '· 정신건강복지센터']] },
    { id: 'lonely', step: '개입 · 연계', title: '고독 · 고립 예방 · 안부 무응답', pages: '2026년 고독 · 고립 예방 및 관리 사업 운영 지침', sum: '안부 앱 장기 무응답은 바로 확인',
      items: ['안부 앱 48시간 무응답 → 안부 전화 → 연결되지 않으면 방문 확인(생활지원사 · 행정복지센터 협조)',
        '식사 거름 반복, 외출 중단, 연락 두절은 고립 위험 신호로 보고 위기도를 다시 평가',
        '문이 잠겨 있고 응답이 없으며 생명 위험이 의심되면 119 · 112에 요청',
        '관계망 넓히기: 경로당 · 노인복지관 프로그램, 이웃 · 자원봉사자 안부 연계'],
      laws: [['ld', '· 고독사 위험자 발굴 · 지원']] },
    { id: 'eplink', step: '개입 · 연계', title: '학대 정황 발견 시 노인보호전문기관 연계', pages: '2026년 노인보건복지사업안내', sum: '보조 기능 · 정황이 보이면 노인보호전문기관(1577-1389) 연계 검토',
      items: ['상담 중 학대 정황(상처 설명이 맞지 않음, 돈 · 재산 문제, 돌봄 방치, 두려움 표현 등)이 보이면 노인보호전문기관 연계를 검토',
        '노인복지법에 따라 직무 중 학대를 알게 된 종사자는 노인보호전문기관 또는 수사기관에 알려야 할 의무가 있음(제39조의6, 원문은 국가법령정보센터에서 확인)',
        '정황은 어르신 말씀 그대로, 관찰한 사실과 해석을 나눠 기록. 상담사가 학대 여부를 판정하지 않음',
        '어르신께 연계 이유와 절차를 설명하고 의사를 존중하되, 생명 · 안전이 위급하면 112 · 119 요청',
        '연계 후에도 상담 관계를 유지하며 정서 지원을 이어감'],
      laws: [['ow', '제39조의6']] },
    { id: 'visit', step: '방문 상담', title: '방문 상담 · 안부 확인 방문 수칙', pages: '기관 시니어 상담 매뉴얼', sum: '미리 연락드리고, 행선지를 공유하고, 필요하면 2인 방문',
      items: ['방문 전에 어르신께 날짜 · 시간을 전화로 미리 알리고, 전날 한 번 더 확인',
        '행선지와 복귀 예정 시간을 동료에게 알리고, 갈등이 있는 가족과 함께 사시면 2인 방문 고려',
        '낙상 위험, 냉난방, 식사 · 약 보관 등 생활환경을 함께 살피되 허락 없이 물건을 만지지 않기',
        '쓰러짐 · 의식 저하 등 위급 상황은 119 먼저, 위협을 느끼면 바로 자리를 피하고 112 요청'],
      laws: [] },
    { id: 'check', step: '점검', title: '사례 점검 · 위기도 재평가', pages: 'S-07 상담일지 · 사례관리 점검표', sum: '정기 점검과 척도 재측정으로 변화를 확인',
      items: ['상담일지(S-07)에 회차 · 일시 · 장소(내방 / 방문 / 전화 / 화상) · 정서 상태 · 개입 · 연계 · 다음 계획을 남기기',
        '위기도는 상담마다 다시 확인하고, 올라가면 슈퍼바이저와 바로 협의',
        '척도(SGDS-K · 외로움 척도 등)는 일정 간격으로 다시 측정해 전후를 비교',
        '연계한 서비스가 실제로 시작됐는지, 어르신이 만족하시는지 확인'],
      laws: [] },
    { id: 'close', step: '종결', title: '종결 사유 · 종결보고서', pages: 'S-08 사례관리 종결보고서', sum: '어르신과 함께 정리하고 종결 이유를 남김',
      items: ['종결 사유: 목표 달성 · 타 기관 연계 · 장기요양 전환 · 시설 입소 · 이사 · 본인 중단 요청 · 사망',
        '종결은 어르신과 미리 이야기 나누고, 다시 도움이 필요하시면 언제든 연락하실 수 있음을 안내',
        'S-08에 목표 달성 정도, 척도 전후 비교, 연계 현황, 사후 관리 계획을 기록',
        '본인 중단 요청은 존중하되, 위기도가 높으면 연계 기관과 안부 확인 체계를 남겨 두기'],
      laws: [['pr', '제21조 (개인정보의 파기)']] },
    { id: 'follow', step: '사후관리', title: '종결 후 안부 확인', pages: '기관 시니어 상담 매뉴얼', sum: '종결 후 1개월 · 3개월 안부 확인',
      items: ['종결 후 1개월 · 3개월에 안부 전화나 안부 앱으로 일상이 유지되는지 확인',
        '위기 재발 신호가 보이면 다시 접수해 초기상담부터 진행',
        '사별 · 애도, 삶의 정리를 원하시면 관련 프로그램을 안내(사전연명의료의향서는 등록기관 안내만)'],
      laws: [] },
    { id: 'l_ow', kind: 'law', step: '노인복지법', title: '상담 · 돌봄 근거와 학대 발견 시 연계', pages: '주제 요약', sum: '노인복지관 상담, 노인맞춤돌봄 근거, 노인보호전문기관 연계 의무',
      items: ['노인복지관 등 여가복지시설의 상담 · 교육 · 사회참여 프로그램 운영 근거',
        '노인맞춤돌봄서비스 등 홀로 지내시는 어르신 지원 사업의 근거',
        '노인보호전문기관을 통한 학대 예방과 연계 체계',
        '제39조의6: 직무 중 학대를 알게 된 종사자의 노인보호전문기관 · 수사기관 알림 의무(조문 원문은 국가법령정보센터에서 확인)'],
      laws: [['ow', '전문'], ['ow', '제39조의6']] },
    { id: 'l_ci', kind: 'law', step: '돌봄통합지원법', title: '의료 · 요양 · 돌봄 통합지원 (2026.3.27 시행)', pages: '주제 요약', sum: '살던 곳에서 계속 생활하시도록 의료 · 요양 · 돌봄을 함께 지원',
      items: ['정식 명칭: 의료 · 요양 등 지역 돌봄의 통합지원에 관한 법률',
        '노쇠 · 질병 등으로 일상생활이 어려운 분이 지역사회에서 계속 생활하시도록 의료 · 요양 · 돌봄을 통합 지원',
        '읍 · 면 · 동 통합돌봄 창구에서 상담 · 신청을 받고, 필요도를 확인해 개인별 지원계획을 세움',
        '상담 중 통합지원이 필요해 보이면 어르신 동의를 받아 창구로 연계'],
      laws: [['ci', '전문']] },
    { id: 'l_sp', kind: 'law', step: '자살예방법', title: '자살위험자 지원 · 생명존중', pages: '주제 요약', sum: '자살 위험이 있는 분의 발견 · 지원 · 연계 체계',
      items: ['정식 명칭: 자살예방 및 생명존중문화 조성을 위한 법률',
        '국가 · 지방자치단체의 자살예방과 자살위험자 지원 책무, 게이트키퍼 교육 등의 근거',
        '자살예방상담전화 109 안내, 위기 시 정신건강복지센터 · 자살예방센터로 연계',
        '연계 시 본인 동의를 우선하되, 생명이 급박하게 위험하면 119 · 112 요청'],
      laws: [['sp', '전문']] },
    { id: 'l_mh', kind: 'law', step: '정신건강복지법', title: '정신건강복지센터 · 지역 정신건강 서비스', pages: '주제 요약', sum: '우울 · 자살 위험 어르신의 전문 상담 · 사례관리 연계',
      items: ['지역 정신건강복지센터의 상담 · 사례관리 · 위기 지원 근거',
        'SGDS-K 선별 결과가 기준 이상이거나 자살 위험이 있으면 연계 검토',
        '입원 등 치료 결정은 상담사 업무가 아니며 전문기관 · 의료기관이 판단'],
      laws: [['mh', '전문']] },
    { id: 'l_dm', kind: 'law', step: '치매관리법', title: '치매안심센터 · 조기 선별', pages: '주제 요약', sum: '인지 변화가 보이면 진단 대신 선별검사로 연계',
      items: ['보건소 치매안심센터의 선별검사 · 상담 · 쉼터 · 가족 지원',
        '상담사는 진단하지 않음 · 인지 변화가 관찰되면 어르신 동의를 받아 선별검사 연계',
        '치매상담콜센터 1899-9988 안내'],
      laws: [['dm', '전문']] },
    { id: 'l_ld', kind: 'law', step: '고독사예방법', title: '고독사 위험자 발굴 · 지원', pages: '주제 요약', sum: '고립된 어르신의 조기 발견과 사회관계망 지원',
      items: ['정식 명칭: 고독사 예방 및 관리에 관한 법률',
        '고독사 위험이 있는 분을 일찍 발견하고 안부 확인 · 사회관계 회복을 지원하는 근거',
        '안부 앱 장기 무응답 알림과 방문 확인 절차의 배경'],
      laws: [['ld', '전문']] },
    { id: 'l_ltc', kind: 'law', step: '노인장기요양보험법', title: '장기요양 인정 · 급여', pages: '주제 요약', sum: '일상생활에 도움이 많이 필요하신 분의 장기요양 이용',
      items: ['혼자서 일상생활이 어려운 분에게 방문요양 · 주야간보호 · 시설급여 등을 제공',
        '국민건강보험공단에 인정 신청 → 등급 판정 후 이용',
        '장기요양으로 전환되면 사례 종결 또는 연계 유지를 검토'],
      laws: [['ltc', '전문']] },
    { id: 'l_pr', kind: 'law', step: '개인정보 보호법', title: '수집 · 제공 · 민감정보 · 파기', pages: '주제 요약', sum: '동의 범위 안에서만 수집 · 공유',
      items: ['수집 · 이용(제15조)과 제3자 제공(제17조)은 원칙적으로 정보주체 동의가 필요',
        '건강 정보 등 민감정보는 별도 동의를 받아 처리(제23조)',
        '가족에게 상담 내용을 알리는 것도 제공에 해당할 수 있으므로 공유 동의 범위를 확인',
        '보유 기간이 끝난 기록은 파기(제21조)'],
      laws: [['pr', '전문']] },
    { id: 'l_sw', kind: 'law', step: '사회복지사업법', title: '사회복지서비스 제공 · 비밀 유지', pages: '주제 요약', sum: '이용자 인권 존중과 업무상 비밀 유지',
      items: ['사회복지서비스 제공과 이용자 인권 존중의 기본 원칙',
        '업무상 알게 된 비밀을 누설하지 않을 의무(조문은 원문에서 확인)'],
      laws: [['sw', '전문']] },
    { id: 'l_ss', kind: 'law', step: '사회보장급여법', title: '위기가구 발굴 · 연계', pages: '주제 요약', sum: '경제 · 주거 위기 어르신을 행정복지센터와 연결',
      items: ['정식 명칭: 사회보장급여의 이용 · 제공 및 수급권자 발굴에 관한 법률',
        '지원이 필요한 분을 발견하면 관할 행정복지센터에 알려 지원으로 연계',
        '경제적 어려움 · 주거 위기를 호소하시는 어르신은 위기가구 지원 상담으로 연결'],
      laws: [['ss', '전문']] },
    { id: 'm_guide', kind: 'man', step: '지침', title: '2026년 노인보건복지사업안내 (보건복지부)', pages: '보건복지부', sum: '시니어 복지 사업 전반의 기준',
      items: ['노인맞춤돌봄 · 노인복지관 · 노인보호전문기관 등 사업별 대상 · 내용 · 절차',
        '사업 기준은 해마다 바뀔 수 있으므로 최신판 원문을 확인'],
      laws: [['ow', '전문']] },
    { id: 'm_care', kind: 'man', step: '지침', title: '노인맞춤돌봄서비스 사업안내', pages: '보건복지부', sum: '안부 확인 · 생활지원 · 사회참여 서비스',
      items: ['수행기관 · 전담사회복지사 · 생활지원사의 역할',
        '안부 확인, 생활교육, 사회참여, 연계 서비스의 내용과 대상',
        '생활지원사 의뢰 사례는 수행기관과 역할을 나눠 협력'],
      laws: [['ow', '· 노인맞춤돌봄서비스 근거']] },
    { id: 'm_iso', kind: 'man', step: '지침', title: '2026년 고독 · 고립 예방 및 관리 사업 운영 지침', pages: '보건복지부', sum: '고립 위험 발굴 · 안부 확인 · 관계망 지원',
      items: ['고립 · 고독사 위험군 발굴과 안부 확인 체계',
        '사회관계망 형성 프로그램과 지역 자원 연계'],
      laws: [['ld', '전문']] },
    { id: 'm_dmc', kind: 'man', step: '지침', title: '치매안심센터 사업안내', pages: '보건복지부', sum: '선별검사 · 쉼터 · 가족 지원',
      items: ['치매 선별검사와 이후 진단 연계 흐름',
        '쉼터 · 인지 프로그램 · 가족 지원 프로그램'],
      laws: [['dm', '전문']] },
    { id: 'm_mh', kind: 'man', step: '지침', title: '정신건강사업안내', pages: '보건복지부', sum: '정신건강복지센터 · 자살예방 사업',
      items: ['정신건강복지센터의 상담 · 사례관리 · 위기 대응',
        '자살 고위험군 연계와 사후 관리'],
      laws: [['mh', '전문'], ['sp', '전문']] },
    { id: 'm_gk', kind: 'man', step: '교육', title: '자살예방 게이트키퍼 교육 (보고듣고말하기 노인용)', pages: '자살예방 교육 자료', sum: '보고 · 듣고 · 말하기로 위기 신호에 대응',
      items: ['보기: 말 · 행동 · 상황에서 자살 위험 신호 알아차리기',
        '듣기: 자살 생각을 직접 묻고, 판단 없이 끝까지 듣기',
        '말하기: 109 · 정신건강복지센터 등 전문기관으로 안전하게 연결'],
      laws: [['sp', '전문']] },
    { id: 'toc', step: '원문', title: '참고 자료 목록', pages: '법령 10종 · 지침 7종', sum: '이 화면의 요약이 바탕으로 삼은 자료',
      items: ['법령 — 노인복지법, 돌봄통합지원법(2026.3.27 시행), 정신건강복지법, 자살예방법, 치매관리법, 고독사예방법, 노인장기요양보험법, 개인정보 보호법, 사회복지사업법, 사회보장급여법',
        '지침 — 2026년 노인보건복지사업안내(보건복지부), 노인맞춤돌봄서비스 사업안내, 2026년 고독 · 고립 예방 및 관리 사업 운영 지침, 치매안심센터 사업안내, 정신건강사업안내',
        '교육 · 내부 자료 — 자살예방 게이트키퍼 교육(보고듣고말하기 노인용), 기관 시니어 상담 매뉴얼, 기관 서식 S-01 ~ S-08',
        '주요 연락처 — 자살예방상담 109 · 보건복지상담센터 129 · 치매상담콜센터 1899-9988 · 노인보호전문기관 1577-1389(학대 의심 시) · 응급 119 · 경찰 112',
        '조문 원문과 개정 여부는 국가법령정보센터에서 확인'],
      laws: [['ow', '전문'], ['ci', '전문']] }
  ];
  const QA = [
    { k: ['자살', '죽고', '109', '위기 개입', '위기개입', '극단'], ref: 'crisis', a: '자살 위험 신호가 보이면 다른 업무보다 먼저 확인해요. 자살 생각을 직접, 차분하게 여쭙고 판단 없이 끝까지 들어 주세요. 혼자 계시지 않도록 하고 109(자살예방상담) · 정신건강복지센터로 연결하며, 급박하면 119 · 112에 요청해요. 개입 후 24시간 안에 안부를 확인하고 S-04 · S-07에 기록해 주세요.' },
    { k: ['동의', '가족 공유', '가족에게', '공유', '녹음', '대리'], ref: 'consent', a: '어르신은 판단능력 있는 성인이라 본인 동의가 원칙이에요. 가족 공유 범위(공유 동의 / 일부 동의 / 미동의)를 따로 여쭙고, 범위 밖 내용은 가족에게 전하지 않아요. 건강 정보는 민감정보라 별도 동의가 필요하고(개인정보 보호법 제23조), 녹음도 따로 동의를 받아요. 생명이 위험한 경우는 비밀보장의 예외예요.' },
    { k: ['치매', '기억력', '인지', '선별검사'], ref: 'assess', a: '상담사는 치매를 진단하지 않아요. 같은 질문 반복, 날짜 혼동, 약 복용 잊음, 길 잃음 같은 변화를 S-06에 관찰한 그대로 기록하고, 어르신 동의를 받아 치매안심센터 선별검사로 연계해요. 가족 상담에는 치매상담콜센터 1899-9988도 안내할 수 있어요.' },
    { k: ['우울', 'SGDS', '척도', '사정'], ref: 'assess', a: 'S-03 단축형 노인우울척도(SGDS-K)는 15문항 예/아니오로 답하는 선별 도구예요. 결과는 진단이 아니며, 기준 이상이면 정신건강복지센터 연계를 검토해요. 우울 점수가 높으면 S-04 자살위험 선별도 함께 확인해 주세요.' },
    { k: ['학대', '노인보호전문기관', '1577'], ref: 'eplink', a: '상담 중 학대 정황이 보이면 노인보호전문기관(1577-1389) 연계를 검토해요. 노인복지법 제39조의6에 따라 직무 중 학대를 알게 된 종사자는 노인보호전문기관 또는 수사기관에 알릴 의무가 있어요. 상담사는 학대 여부를 판정하지 않고, 어르신 말씀과 관찰 사실을 나눠 기록해 주세요.' },
    { k: ['무응답', '고독사', '고립', '연락 두절', '안부'], ref: 'lonely', a: '안부 앱이 48시간 동안 응답이 없으면 먼저 안부 전화를 드리고, 연결되지 않으면 생활지원사 · 행정복지센터와 함께 방문 확인해요. 생명 위험이 의심되면 119 · 112에 요청해요. 고립 신호가 반복되면 위기도를 다시 평가해 주세요.' },
    { k: ['통합돌봄', '돌봄통합', '통합지원', '창구'], ref: 'l_ci', a: '돌봄통합지원법(2026.3.27 시행)은 어르신이 살던 곳에서 계속 생활하시도록 의료 · 요양 · 돌봄을 통합 지원하는 법이에요. 읍 · 면 · 동 통합돌봄 창구에서 상담 · 신청을 받아요. 상담 중 필요해 보이면 어르신 동의를 받아 창구로 연계해 주세요. 세부 조문은 국가법령정보센터 원문으로 확인해 주세요.' },
    { k: ['연계', '맞춤돌봄', '장기요양', '자원', '복지관'], ref: 'link', a: '노인맞춤돌봄서비스(안부 확인 · 생활지원), 통합돌봄 창구, 방문건강관리(보건소), 치매안심센터, 정신건강복지센터, 노인복지관 프로그램, 장기요양 등급 신청 등을 어르신 욕구에 맞게 연계해요. 연계 기관에 전하는 정보는 어르신 동의 범위 안에서만 전해요.' },
    { k: ['종결', '종결보고서', '사후관리', '사후 관리'], ref: 'close', a: '종결 사유는 목표 달성 · 타 기관 연계 · 장기요양 전환 · 시설 입소 · 이사 · 본인 중단 요청 · 사망 등이에요. S-08 종결보고서에 목표 달성 정도와 척도 전후 비교, 연계 현황을 남기고, 종결 후 1개월 · 3개월에 안부를 확인해요.' },
    { k: ['접수', '의뢰', '의뢰인'], ref: 'intake', a: '접수할 때는 의뢰 경로(본인 · 가족 · 행정복지센터 · 생활지원사 · 의료기관 · 치매안심센터 등)와 주호소를 의뢰인의 표현 그대로 기록하고, 어르신 본인이 상담을 알고 원하시는지 확인해요. 정서 · 위기 신호가 있으면 일반 절차보다 위기 개입을 먼저 해요.' },
    { k: ['방문', '가정방문', '신변', '안전'], ref: 'visit', a: '방문 전에 날짜 · 시간을 미리 알리고 전날 다시 확인해요. 행선지와 복귀 시간을 동료에게 알리고, 갈등이 있는 가족과 함께 사시면 2인 방문을 고려해요. 위급 상황은 119 먼저, 위협을 느끼면 바로 자리를 피하고 112에 요청해요.' },
    { k: ['호칭', '의사소통', '보청기', '존댓말', '청력'], ref: 'comm', a: '청력 · 시력을 먼저 확인하고 조용한 곳에서 천천히 말씀드려요. 안내문은 큰 글씨로, 중요한 내용은 한 번 더 확인해요. 선호 호칭을 여쭙고 기록하며, 반말 · 유아어 · 낮잡는 말은 쓰지 않아요. AI 요약도 같은 원칙을 따라요.' },
    { k: ['개인정보', '민감정보', '파기', '보관'], ref: 'l_pr', a: '개인정보 수집 · 이용(제15조)과 제3자 제공(제17조)은 원칙적으로 동의가 필요하고, 건강 정보 같은 민감정보는 별도 동의를 받아요(제23조). 가족에게 알리는 것도 제공에 해당할 수 있어 공유 동의 범위를 확인해 주세요. 보유 기간이 끝나면 파기해요(제21조).' },
    { k: ['계획', '목표', '위기도'], ref: 'plan', a: '목표는 어르신이 원하시는 변화를 어르신의 말씀으로 담아 작고 구체적으로 세워요. 위기도(일반 · 관심 · 집중 · 위기)에 따라 상담 주기와 안부 확인 빈도를 정하고, 연계 자원은 어르신 동의를 받아 계획에 넣어요.' }
  ];

  const byId = {}; REFS.forEach((r) => { byId[r.id] = r; });
  const law = (pair) => ({ label: LAW[pair[0]][0] + ' ' + pair[1], url: LAW[pair[0]][1] });
  const openRef = (id) => { this._scrollTo = 'ref-' + id; this.setState({ open: { ...this.state.open, [id]: true }, f: 'all', tab: 'ref' }); };
  const answer = (q) => { const t = String(q || '').replace(/\s+/g, ''); let best = null, score = 0;
    QA.forEach((x) => { const sc = x.k.filter((k) => t.includes(k.replace(/\s+/g, ''))).length; if (sc > score) { score = sc; best = x; } });
    if (!best) return { role: 'bot', text: '지침과 법령에서 딱 맞는 내용을 찾지 못했어요. 아래 참고사항과 참고 자료 목록을 확인해 보시거나, 단어를 바꿔 다시 물어봐 주세요.', refs: ['toc'], laws: [['ow', '전문'], ['ci', '전문']] };
    const r = byId[best.ref]; const extra = { crisis: 'm_gk', consent: 'l_pr', eplink: 'l_ow', link: 'l_ci', lonely: 'l_ld', assess: 'l_dm' }[best.ref]; return { role: 'bot', text: best.a, refs: extra ? [best.ref, extra] : [best.ref], laws: r.laws.slice(0, 2) }; };
  const ask = (q) => { const text = String(q || '').trim(); if (!text || this.state.typing) return; clearTimeout(this._tyT); this._msgScroll = true;
    this.setState({ msgs: [...this.state.msgs, { role: 'me', text }], draft: '', typing: true });
    this._tyT = setTimeout(() => { this._msgScroll = true; this.setState({ msgs: [...this.state.msgs, answer(text)], typing: false }); }, 700); };
  const msgs = s.msgs.map((m) => { const refs = (m.refs || []).map((id) => ({ label: byId[id].kind ? byId[id].step + ' ' + byId[id].title.split(' (')[0] : byId[id].step + ' · ' + byId[id].pages, open: () => openRef(id) })); const laws = (m.laws || []).map(law);
    return { cls: m.role === 'me' ? 'lg-u' : 'lg-b', text: m.text, refs, laws, hasRefs: refs.length + laws.length > 0 }; });
  const suggs = ['자살 위험 신호가 보이면 어떻게 해요?', '가족에게 상담 내용을 공유해도 되나요?', '기억력 저하가 걱정되실 때는?', '안부 앱 무응답이 길어지면?', '학대 정황이 보이면 어디에 연계해요?', '통합돌봄 창구 연계는 어떻게 해요?', '우울척도 점수는 어떻게 봐요?', '사례 종결 절차 알려주세요', '방문 상담 때 안전 수칙은?'].map((label) => ({ label, ask: () => ask(label) }));
  const F = s.f || 'all'; const shown = REFS.filter((r) => F === 'all' || (F === 'step' ? !r.kind : r.kind === F));
  const filters = [['all', '전체'], ['step', '업무 단계'], ['law', '관련 법령'], ['man', '매뉴얼 · 지침']].map(([k, label]) => ({ label, cls: F === k ? 'on' : '', on: F === k ? 'true' : 'false', pick: () => this.setState({ f: k }) }));
  const refs = shown.map((r) => { const open = !!s.open[r.id];
    return { ...r, stepCls: r.kind ? 'k-law' : '', domId: 'ref-' + r.id, open, cls: open ? 'open' : '', exp: open ? 'true' : 'false', laws: r.laws.map(law), toggle: () => this.setState({ open: { ...this.state.open, [r.id]: !this.state.open[r.id] } }) }; });
  const TB = s.tab || 'ai'; const tabs = [['ai', '법령 · 매뉴얼 AI에게 묻기'], ['ref', '업무 단계별 참고사항 · 주요 조문']].map(([k, label]) => ({ label, cls: TB === k ? 'on' : '', sel: TB === k ? 'true' : 'false', pick: () => this.setState({ tab: k }) }));
  return { tabs, tabAi: TB === 'ai', tabRef: TB === 'ref', filters, msgs, suggs, refs, typing: s.typing, draft: s.draft, setDraft: (e) => this.setState({ draft: e.target.value }),
    submit: (e) => { if (e && e.preventDefault) e.preventDefault(); ask(this.state.draft); }, openToc: () => openRef('toc'),
    chatReset: () => { clearTimeout(this._tyT); this.setState({ msgs: [this.state.msgs[0]], typing: false, draft: '' }); } };
}
}
