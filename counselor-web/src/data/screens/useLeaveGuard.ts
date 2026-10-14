// 저장하지 않은 수정이 있을 때 화면을 떠나기 전에 묻는다.
//
//  - 화면 안 링크(사이드바 · 위치 표시 · 단계 표시 등 '#/…' 링크)를 누르면 확인창을 띄우고, 취소하면 이동하지 않는다.
//  - 새로고침 · 탭 닫기는 브라우저 기본 확인창으로 묻는다.
//  - 브라우저 뒤로 가기는 막지 못한다(HashRouter 에는 이동 차단 기능이 없다).
// 화면 배치와 상관없이 문서 전체의 링크 누름을 먼저 받아 본다(react-router Link 보다 먼저).

import { useEffect } from "react";

export const LEAVE_MESSAGE = "저장하지 않은 수정이 있습니다. 이 화면을 떠나면 수정이 사라집니다. 떠날까요?";

export function useLeaveGuard(unsaved: boolean): void {
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

    return () => {
      document.removeEventListener("click", onClick, true);
      window.removeEventListener("beforeunload", onUnload);
    };
  }, [unsaved]);
}
