// 초기면접(서식 4 ②) 아동 특성 · 가정상황 고르기 단추 값. 새 사례 등록(caseRegister.ts), 사례 상세의 초기면접 수정
// (caseDetail.ts), 상담 일지의 추가 항목 고르기(noteWrite.ts)가 같은 모양을 쓴다(디자인 CaseRegister.dc.html 의 고르기 단추).

/** 목록에 있으면 빼고, 없으면 뒤에 붙인다(고른 순서대로 저장된다). */
export function toggleItem(list: string[], label: string): string[] {
  return list.includes(label) ? list.filter((item) => item !== label) : [...list, label];
}

/**
 * 하나만 고르는 단추(서식 4 ② 가족유형, 2026-11-05). 모양은 아래 고르기 단추와 같고, 같은 것을 다시 누르면 뺀다.
 * options 는 서버 코드 · 화면 글자, picked 는 지금 코드("" = 고르지 않음). onPick 은 새 코드("" = 뺌)를 받는다.
 */
export function singleChoices(
  options: { value: string; label: string }[],
  picked: string,
  disabled: boolean,
  onPick: (value: string) => void,
) {
  const pickedLabel = options.find((option) => option.value === picked)?.label;

  return intakeChoices(
    options.map((option) => option.label),
    pickedLabel ? [pickedLabel] : [],
    disabled,
    (label) => {
      const option = options.find((item) => item.label === label);
      if (option) onPick(option.value === picked ? "" : option.value);
    },
  );
}

/**
 * 서식 항목마다 고르기 단추 값(눌러서 고르고 다시 눌러 뺀다). disabled 면 눌러도 바뀌지 않는다(저장 · 등록 중).
 * onToggle 은 누른 항목 이름을 받는다. 목록은 부르는 쪽이 지금 상태로 바꾼다(toggleItem).
 */
export function intakeChoices(options: string[], picked: string[], disabled: boolean, onToggle: (label: string) => void) {
  return options.map((label) => {
    const on = picked.includes(label);

    return {
      label,
      on,
      mark: on ? "✓" : "+",
      bg: on ? "#F1EADA" : "#FFFFFF",
      bd: on ? "#2B2A26" : "#DAD5C9",
      fg: "#2B2A26",
      fw: on ? 700 : 400,
      disabled,
      toggle: () => {
        if (!disabled) onToggle(label);
      },
    };
  });
}
