// 서식 4 글 칸 하나(2026-11-05 — 사례연계 경위 · ② 보호자와 아동과의 관계 · 문제력 · 태도 · 환경 · 소견).
// 새 사례 등록(CaseRegister)과 초기면접지(CaseIntake)가 같이 쓴다. f 는 화면 값(caseTextValues): value · onChange · max · placeholder,
// 고칠 수 없을 때 disabled.

export default function FormTextArea({ label, f, style }) {
  return (
    <label className="fl">
      <span className="lb">{label}</span>
      <textarea
        className="ta2"
        maxLength={f.max}
        placeholder={f.placeholder}
        value={f.value}
        onChange={f.onChange}
        disabled={Boolean(f.disabled)}
        style={style}
      ></textarea>
    </label>
  );
}
