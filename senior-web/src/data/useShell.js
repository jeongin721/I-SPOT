// 모든 화면 공통: 로그인 확인 · 내 이름 · 로그아웃. 로그인 안 됐으면 로그인 화면으로 보낸다.
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthSession } from '@cw/data/useAuthSession';

export function useShell() {
  const session = useAuthSession();
  const navigate = useNavigate();
  useEffect(() => {
    if (session.status === 'signedOut' || session.status === 'mustChangePassword') navigate('/Login', { replace: true });
  }, [session.status, navigate]);
  const me = session.me;
  return {
    session,
    ready: session.status === 'signedIn',
    meName: me ? me.name : '',
    meInitial: me && me.name ? me.name.slice(0, 1) : '',
    meRole: me ? (me.role === 'ADMIN' ? '관리자' : '상담사') : '',
    logout: (e) => {
      if (e && e.preventDefault) e.preventDefault();
      session.logout();
    },
  };
}
