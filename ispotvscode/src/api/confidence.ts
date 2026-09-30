// STT 발화 신뢰도(confidence)를 화면에서 읽는 규칙. 신뢰도를 보여 주거나 세는 곳은 모두 이 함수를 쓴다.
// (화면은 adapters.ts 에서 다시 내보낸 것을 가져다 쓴다.)
//
// - 0.0(0 이하)은 "값 없음"이다. STT 공급자가 신뢰도를 주지 않은 경우로, ElevenLabs Scribe 결과는
//   모든 발화가 이렇다(stt/ispot_stt.py 가 confidence 0.0 · is_low_confidence False 로 채운다).
//   측정값 0% 로 보지 않으므로 저신뢰로 세지 않고, 화면에는 숫자 대신 "—" 를 보여 준다.
// - 저신뢰 기준 0.7 은 backend/docs/API_CONTRACT.md 7절("저신뢰 구간 표시는 confidence 로 판단하되
//   (예: < 0.7)")과 backend/app/adapters/ai_adapter.py 의 is_explicitly_low_confidence
//   (0 < confidence < 0.7)와 같다. 그래서 Mock AI 경고 "저신뢰 구간 N건" 과 STT 검수 화면의 저신뢰
//   개수가 같은 규칙으로 세어진다(pipeline · langgraph 는 이 경고를 내지 않는다).
//   기준을 바꿀 때는 Backend 와 계약서도 함께 바꾼다.
// - 한계: 실제로 0% 로 측정된 발화도 값 없음으로 보인다. Backend 도 같은 한계가 있다.
//
// node 로 바로 확인할 수 있게 다른 파일을 import 하지 않는다.

/** 이 값보다 낮으면(0 초과일 때) 저신뢰로 본다. Backend 기준과 같게 둔다. */
export const LOW_CONFIDENCE_THRESHOLD = 0.7;

/** STT 공급자가 준 신뢰도 값이 있는가. 0 이하는 값 없음이다. */
export function hasConfidence(confidence: number): boolean {
  return confidence > 0;
}

/** 값이 있고 기준보다 낮은 발화. 값 없음(0.0)은 저신뢰가 아니다. */
export function isLowConfidence(confidence: number): boolean {
  return hasConfidence(confidence) && confidence < LOW_CONFIDENCE_THRESHOLD;
}

/**
 * 화면에 보여 줄 신뢰도 퍼센트 문구. 값 없음이면 null 이고, 화면은 숫자 대신 "—" 를 보여 준다.
 * - 저신뢰는 내림하고 기준 바로 아래(69%)를 넘지 않게 한다. 반올림하면 0.695 가 "70%" 로 보여
 *   "70% 미만이 저신뢰" 라는 기준과 어긋난다. (+1e-9 는 0.29 * 100 = 28.999… 같은 부동소수 오차 보정)
 * - 저신뢰이면서 1% 가 안 되는 값은 "<1%" 로 보여 값 없음("—")과 구분한다.
 * - 기준 이상은 반올림한다. 기준 이상인 값이 기준 아래 퍼센트로 보이는 일은 없다.
 */
export function formatConfidencePercent(confidence: number): string | null {
  if (!hasConfidence(confidence)) return null;

  if (isLowConfidence(confidence)) {
    const maxLowPct = Math.round(LOW_CONFIDENCE_THRESHOLD * 100) - 1;
    const pct = Math.min(Math.floor(confidence * 100 + 1e-9), maxLowPct);
    return pct < 1 ? "<1%" : `${pct}%`;
  }

  return `${Math.round(confidence * 100)}%`;
}
