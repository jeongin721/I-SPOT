// 저장하지 않은 수정이 있을 때 화면을 떠나기 전에 묻는다.
//
//  - 화면 안 링크(사이드바 · 위치 표시 · 단계 표시 등 '#/…' 링크)를 누르면 확인창을 띄우고, 취소하면 이동하지 않는다.
//  - 새로고침 · 탭 닫기는 브라우저 기본 확인창으로 묻는다.
//  - 브라우저 뒤로 가기는 guardBack 을 켠 화면에서만 묻는다(기관 서식 · 종결보고서, Codex #140 M5, 11/03). HashRouter 에는 이동
//    차단 기능이 없어서, 수정이 생기면 지금 주소를 방문 기록에 한 칸 더 넣어 둔다. 뒤로 가기를 누르면 그 칸만 빠져 화면은
//    그대로이고 여기서 묻는다 — 떠나면 한 번 더 뒤로 가고, 남으면 칸을 다시 넣는다. 저장해서 수정이 없어지면 넣은 칸을 뺀다.
// 화면 배치와 상관없이 문서 전체의 링크 누름을 먼저 받아 본다(react-router Link 보다 먼저).

import { useEffect } from "react";

export const LEAVE_MESSAGE = "저장하지 않은 수정이 있습니다. 이 화면을 떠나면 수정이 사라집니다. 떠날까요?";

/** 뒤로 가기를 묻으려고 넣은 방문 기록 칸 표시. */
const BACK_GUARD = "ispotLeaveGuard";

export interface LeaveGuardOptions {
  /** 브라우저 뒤로 가기도 묻는다. 기본 false. */
  guardBack?: boolean;
}

function pushBackGuard(): void {
  window.history.pushState({ ...(window.history.state ?? {}), [BACK_GUARD]: true }, "", window.location.href);
}

export function useLeaveGuard(unsaved: boolean, { guardBack = false }: LeaveGuardOptions = {}): void {
  useEffect(() => {
    if (!unsaved) return;

    const onClick = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

      const link = (event.target as Element | null)?.closest?.("a[href]");
      const href = link?.getAttribute("href") ?? "";

      if (!href.startsWith("#/") || href === window.location.hash) return;
      if (window.confirm(LEAVE_MESSAGE)) return;

      event.preventDefault();
      event.stopPropagation();
    };

    const onUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };

    document.addEventListener("click", onClick, true);
    window.addEventListener("beforeunload", onUnload);

    // 뒤로 가기: 넣어 둔 칸에서 같은 주소의 원래 칸으로 돌아온 때만 묻는다.
    const href = window.location.href;
    let leaving = false;
    const onPop = () => {
      if (leaving || window.location.href !== href || window.history.state?.[BACK_GUARD]) return;
      if (window.confirm(LEAVE_MESSAGE)) {
        leaving = true;
        window.history.back();
        return;
      }
      pushBackGuard();
    };
    if (guardBack) {
      pushBackGuard();
      window.addEventListener("popstate", onPop);
    }

    return () => {
      document.removeEventListener("click", onClick, true);
      window.removeEventListener("beforeunload", onUnload);
      if (!guardBack) return;
      window.removeEventListener("popstate", onPop);
      // 저장해서 수정이 없어졌으면(같은 주소에 그대로 있음) 넣어 둔 칸을 뺀다. 다른 화면으로 옮겨 간 뒤에는 건드리지 않는다.
      if (!leaving && window.location.href === href && window.history.state?.[BACK_GUARD]) window.history.back();
    };
  }, [unsaved, guardBack]);
}
