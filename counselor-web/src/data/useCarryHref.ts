// 예시 화면(아직 서버와 연결하지 않은 화면)의 링크에 지금 화면의 사례 · 회차 ID 를 붙인다.
//
// 예시 화면은 링크를 '/NoteWrite' 처럼 경로만 갖고 있다. 연결된 화면에서 ?case=&session= 을 달고
// 예시 화면으로 들어온 뒤 그 화면의 단계 링크로 돌아가면 ID 가 빠져 빈 화면이 됐다(10/16 시연).
// ID 없이 들어온 예시 화면(사이드바 등)은 지금처럼 경로만 쓴다.
import { useSearchParams } from "react-router-dom";
import { carryScreenHref, readScreenIds } from "./screens/links";

export function useCarryHref(): (page: string) => string {
  const ids = readScreenIds(useSearchParams()[0]);

  return (page) => carryScreenHref(page, ids);
}
