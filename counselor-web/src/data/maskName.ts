// 이름 가리기(10/29 디자인 nmMask): 이름의 둘째 글자를 ○ 로 — 이서윤 → 이○윤, 성을 뺀 서윤 → 서○.
// 인쇄 · 복사할 때만 쓰고 저장된 글은 바꾸지 않는다. 서버에는 실명이 없어 사례 별칭을 가린다.
export function maskName(text: string, name: string): string {
  if (!name || name.length < 2) return text;
  const given = name.slice(1);
  const full = text.split(name).join(name[0] + "○" + name.slice(2));
  return given.length >= 2 ? full.split(given).join(given[0] + "○" + given.slice(2)) : full;
}

/** 고르기 창의 예시 문구(예: 이○윤 · 서○). */
export function maskExample(name: string): string {
  return name.length >= 3 ? `${maskName(name, name)} · ${maskName(name.slice(1), name)}` : maskName(name, name);
}
