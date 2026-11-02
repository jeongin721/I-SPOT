// 계정에 묶인 검색어. 실명을 보이고 찾는 목록(사례 목록 · 녹취 올리기 · 관리자 사례 목록 · 종결 검토)이 쓴다.
// 같은 브라우저에서 다른 계정으로 바뀌어도(다른 탭에서 다시 로그인 등) 앞 계정이 친 이름이 검색칸에 남거나
// 그 이름으로 새 요청이 나가지 않게 한다(Codex #130 H1).

import { useCallback, useEffect, useState } from "react";

import type { AuthSession } from "./useAuthSession";

/**
 * 로그인 확인 중이거나 다른 계정으로 바뀌면 바뀐 첫 그리기부터 빈 검색어로 보이고
 * 들고 있던 검색어도 버린다(같은 계정으로 다시 확인돼도 비운다). 로그인이 확인되기 전에 친 글자는 받지 않는다.
 */
export function useAccountSearch(session: AuthSession): [string, (value: string) => void] {
  const owner = session.status === "signedIn" && session.me ? session.me.id : null;
  const [held, setHeld] = useState<{ owner: string | null; value: string }>({ owner: null, value: "" });

  useEffect(() => {
    setHeld((current) => (current.owner === owner ? current : { owner, value: "" }));
  }, [owner]);

  const setSearch = useCallback((value: string) => {
    if (owner !== null) setHeld({ owner, value });
  }, [owner]);

  return [owner !== null && held.owner === owner ? held.value : "", setSearch];
}
