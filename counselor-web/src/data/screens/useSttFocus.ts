// STT 검수: 주소의 seg(발화 ID)가 가리키는 줄로 한 번 스크롤한다(10/21 디자인의 '근거 원문 위치로 이동').
//
// 디자인은 다른 화면이 브라우저 저장소(ispot-stt)에 시간('00:41')을 적고, STT 검수가 300ms 마다 그 값을 읽어
// id="ln-0041" 줄을 찾는다(componentDidUpdate). 앱은 저장소 · 되풀이 확인 없이 주소 쿼리(?session=…&seg=<발화 ID>)로 받는다.
// 시간이 아니라 발화 ID 로 찾고, 발화 ID 는 회차마다 seg_001 부터라 회차 ID 와 함께 본다.
//
// 돌려주는 ref 를 그 줄에 붙이면 줄이 처음 그려질 때(원문을 받은 뒤) 한 번만 스크롤한다. 보기를 바꿔 줄이 다시 그려져도
// 같은 회차 · 발화면 다시 스크롤하지 않는다.

import { useCallback, useRef } from "react";

export function useSttFocus(sessionId: string | null, segmentId: string | null): (element: HTMLElement | null) => void {
  const target = sessionId && segmentId ? `${sessionId}:${segmentId}` : null;
  const scrolled = useRef<string | null>(null);

  return useCallback(
    (element: HTMLElement | null) => {
      if (!element || !target || scrolled.current === target) return;

      scrolled.current = target;
      element.scrollIntoView({ behavior: "smooth", block: "center" });
    },
    [target],
  );
}
