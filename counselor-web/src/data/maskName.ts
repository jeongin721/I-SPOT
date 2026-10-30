// 이름 가리기(10/29 디자인 nmMask): 이름의 둘째 글자를 ○ 로 — 이서윤 → 이○윤, 성을 뺀 서윤 → 서○.
// 인쇄 · 복사할 때만 쓰고 저장된 글은 바꾸지 않는다. 가릴 이름은 그 사례에 등록된 이름 전부(personalNames)와 별칭이다.
// 한 글자 이름('솔')은 그 글자를 ○ 로 — 다른 낱말 속 같은 글자도 가려지지만 이름이 새는 것보다 낫다(민규 #122 교차검증).
export function maskName(text: string, name: string): string {
  if (!name) return text;
  if ([...name].length === 1) return text.split(name).join("○");
  const given = name.slice(1);
  const full = text.split(name).join(name[0] + "○" + name.slice(2));
  return given.length >= 2 ? full.split(given).join(given[0] + "○" + given.slice(2)) : full;
}

/** 이름 여러 개를 가린다. 긴 이름부터 가려 '한가람' 이 '가람' 보다 먼저 걸리게 한다. 빈 이름 · 겹친 이름은 뺀다. */
export function maskNames(text: string, names: string[]): string {
  const list = [...new Set(names.map((name) => name.trim()).filter(Boolean))].sort((a, b) => [...b].length - [...a].length);
  return list.reduce((current, name) => maskName(current, name), text);
}

/** 고르기 창의 예시 문구(예: 이○윤 · 서○). */
export function maskExample(name: string): string {
  return [...name].length >= 3 ? `${maskName(name, name)} · ${maskName(name.slice(1), name)}` : maskName(name, name);
}
