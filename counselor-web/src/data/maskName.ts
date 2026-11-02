// 이름 가리기(10/29 디자인 nmMask): 이름의 둘째 글자를 ○ 로 — 이서윤 → 이○윤, 성을 뺀 서윤 → 서○.
// 인쇄 · 복사할 때만 쓰고 저장된 글은 바꾸지 않는다. 서버에는 실명이 없어 사례 별칭을 가린다.
// 한 글자 별칭('솔')은 그 글자를 ○ 로 — 다른 낱말 속 같은 글자도 가려지지만 이름이 새는 것보다 낫다(민규 #122 교차검증).
export function maskName(text: string, name: string): string {
  if (!name) return text;
  // 코드포인트로 나눈다(이모지 등 UTF-16 두 단위 글자가 반으로 잘려 깨지지 않게 — 민규 #122 재검증).
  const chars = [...name];
  if (chars.length === 1) return text.split(name).join("○");
  const given = chars.slice(1);
  const full = text.split(name).join(chars[0] + "○" + chars.slice(2).join(""));
  return given.length >= 2 ? full.split(given.join("")).join(given[0] + "○" + given.slice(2).join("")) : full;
}

/** 고르기 창의 예시 문구(예: 이○윤 · 서○). */
export function maskExample(name: string): string {
  const chars = [...name];
  return chars.length >= 3 ? `${maskName(name, name)} · ${maskName(chars.slice(1).join(""), name)}` : maskName(name, name);
}
