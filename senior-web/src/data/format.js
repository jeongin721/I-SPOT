// 화면 표시용 작은 변환들. 서버에 없는 값은 '—' 로 둔다(디자인 칸은 그대로).
export const DASH = '—';
const DAYS = ['일', '월', '화', '수', '목', '금', '토'];
const pad = (n) => String(n).padStart(2, '0');

export function ymd(value) {
  if (!value) return DASH;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value).slice(0, 10);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
export function md(value) {
  if (!value) return DASH;
  const d = new Date(value);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}
export function hm(value) {
  if (!value) return '';
  const d = new Date(value);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
export function dayName(value) {
  return DAYS[new Date(value).getDay()];
}
export function age(birthYear) {
  if (!birthYear) return null;
  return new Date().getFullYear() - Number(birthYear);
}
export function genderLabel(g) {
  return g === 'F' || g === 'FEMALE' ? '여' : g === 'M' || g === 'MALE' ? '남' : DASH;
}
export function or(value) {
  return value === null || value === undefined || value === '' ? DASH : value;
}
