// 화면 사이 이동 주소. 사례 · 회차는 ?case= · ?session= 로 넘긴다(counselor-web 과 같은 방식).
import { useLocation } from 'react-router-dom';

export function useIds() {
  const q = new URLSearchParams(useLocation().search);
  return { caseId: q.get('case'), sessionId: q.get('session'), sec: q.get('sec') };
}

export function href(page, ids = {}) {
  const q = new URLSearchParams();
  if (ids.caseId) q.set('case', ids.caseId);
  if (ids.sessionId) q.set('session', ids.sessionId);
  if (ids.sec) q.set('sec', ids.sec);
  const s = q.toString();
  return `#/${page}${s ? `?${s}` : ''}`;
}

/** 디자인의 '#/화면' 링크에 지금 사례 · 회차를 붙인다(사이드바 · 단계 이동). */
export function carry(link, ids) {
  if (typeof link !== 'string' || !link.startsWith('#/') || link.startsWith('#/Soon')) return link;
  const [path, query] = link.slice(2).split('?');
  const q = new URLSearchParams(query || '');
  return href(path, { caseId: ids.caseId, sessionId: ids.sessionId, sec: q.get('sec') });
}
