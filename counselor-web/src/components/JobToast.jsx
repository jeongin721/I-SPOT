// 화면 위쪽 '분석 중입니다... → 분석 완료 [검수]' 알림(10/22 디자인의 job-toast). App.jsx 가 모든 화면 위에 한 번 그린다.
// 값은 src/data/transcriptionJobs.ts(녹취 올리기 · 녹음 저장 뒤 원문 변환을 화면과 상관없이 따라가는 저장소)에서 온다.
//  - 가장 최근에 맡긴 회차 하나만 보인다. '검수' 를 누르면 그 회차의 STT 검수로 가고 알림을 닫는다.
//  - 로그인 화면 · 시작 화면에서는 보이지 않는다(디자인: 로그인 제외).
//  - 로그인은 useAuthSession 대신 토큰으로 본다(그 훅은 쓰는 곳마다 상태가 따로라, 로그인 화면에서 먼저 그려진 이 알림은 같은 탭의
//    로그인을 모른다). 맡길 때의 토큰과 지금 토큰이 다르면(로그아웃 · 다른 계정 · 다시 로그인) 버린다 — 화면을 옮길 때, 다른 탭에서
//    토큰이 바뀔 때(storage 이벤트), 저장소가 조회할 때마다 본다.
// 디자인 문구 '분석' 은 여기서는 원문 변환(STT)을 뜻한다. AI 분석은 STT 검수 · 원문 확정 뒤에 따로 요청한다.
import { useEffect, useSyncExternalStore } from 'react';
import { useLocation } from 'react-router-dom';
import A from './A';
import { screenHref } from '../data/screens/links';
import {
  dismissTranscription,
  dropStaleTranscriptionJobs,
  getTranscriptionJobs,
  subscribeTranscriptionJobs,
} from '../data/transcriptionJobs';
import { useTheme } from '../theme';

const HIDDEN_PAGES = new Set(['/login', '/landing']);

export default function JobToast() {
  const jobs = useSyncExternalStore(subscribeTranscriptionJobs, getTranscriptionJobs);
  const { pathname } = useLocation();
  const theme = useTheme();

  // 화면을 옮길 때 토큰이 달라진 일을 버린다.
  useEffect(() => {
    dropStaleTranscriptionJobs();
  }, [pathname]);

  // 다른 탭에서 로그아웃 · 다시 로그인하면(localStorage 토큰 칸) 바로 버린다.
  useEffect(() => {
    const onStorage = () => dropStaleTranscriptionJobs();
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  if (HIDDEN_PAGES.has(pathname.toLowerCase())) return null;

  const job = jobs.reduce((latest, item) => (!latest || item.seq > latest.seq ? item : latest), null);

  if (!job) return null;

  return (
    <div className={theme.cls}>
      <div className="job-toast" role="status" aria-live="polite">
        {job.phase === 'run' ? (
          <>
            <span className="job-spin" aria-hidden="true"></span>
            <span>분석 중입니다...</span>
            <span className="job-file">{job.name}</span>
          </>
        ) : null}
        {job.phase === 'done' ? (
          <>
            <span className="job-ok" aria-hidden="true">
              ✓
            </span>
            <span>분석 완료</span>
            <A
              className="job-go"
              to={screenHref('/SttReview', { caseId: job.caseId, sessionId: job.sessionId })}
              onClick={() => dismissTranscription(job.sessionId)}
            >
              검수
            </A>
          </>
        ) : null}
        {job.phase === 'failed' ? (
          <>
            <span className="job-ok" aria-hidden="true">
              !
            </span>
            <span>원문 변환에 실패했어요</span>
            <A
              className="job-go"
              to={screenHref('/SttReview', { caseId: job.caseId, sessionId: job.sessionId })}
              onClick={() => dismissTranscription(job.sessionId)}
            >
              다시 변환
            </A>
          </>
        ) : null}
      </div>
    </div>
  );
}
