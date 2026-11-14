// 장치 표본율(44.1 · 48kHz 등)의 마이크 소리를 16kHz 로 줄인다(녹음기 useRecorder 가 쓴다).
//
// 줄이기 전에 저역 통과 필터(창 씌운 sinc FIR, 차단 7kHz)를 거친다. 거르지 않고 줄이면 8kHz 위 소리(ㅅ · ㅆ · ㅊ 의 치찰음 등)가
// 말소리 대역으로 접혀 들어와 원문 변환을 흐린다(민규 #169 — 11kHz 음이 같은 크기로 파일에 남았다).
// 녹음기는 먼저 오디오를 16kHz 로 열어 브라우저가 거르게 하고(그때는 이 필터를 거치지 않는다), 그게 안 되는 브라우저에서만 이것을 쓴다.

export interface Resampler {
  /** 장치 표본(-1~1)을 받아 16kHz 표본(-1~1)을 돌려준다. 묶음 사이의 상태를 이어 간다. */
  push(input: Float32Array): Float32Array;
}

/** 줄일 때 쓰는 FIR 길이(홀수). 48kHz 에서 약 1.3ms — 실시간으로 넉넉하다. */
const TAPS = 63;

/** 창(Blackman) 씌운 sinc 저역 통과 필터 계수. cutoff 는 표본율에 대한 비(0~0.5). */
function lowpass(cutoff: number): Float32Array {
  const taps = new Float32Array(TAPS);
  const mid = (TAPS - 1) / 2;
  let sum = 0;

  for (let n = 0; n < TAPS; n += 1) {
    const x = n - mid;
    const sinc = x === 0 ? 2 * cutoff : Math.sin(2 * Math.PI * cutoff * x) / (Math.PI * x);
    const w = 0.42 - 0.5 * Math.cos((2 * Math.PI * n) / (TAPS - 1)) + 0.08 * Math.cos((4 * Math.PI * n) / (TAPS - 1));

    taps[n] = sinc * w;
    sum += taps[n];
  }
  for (let n = 0; n < TAPS; n += 1) taps[n] /= sum;

  return taps;
}

export function makeResampler(fromRate: number, toRate = 16_000): Resampler {
  const step = fromRate / toRate;

  // 같거나 더 낮은 표본율이면 거르지 않고 선형 보간만 한다.
  const filter = step > 1 ? lowpass(Math.min(0.5, 7_000 / fromRate)) : null;
  // 필터 앞 표본(앞 묶음의 끝 TAPS-1 개를 이어 붙여 거른다).
  let history = new Float32Array(filter ? TAPS - 1 : 0);
  // 다음 출력 표본의 위치(거른 표본 기준, 음수면 앞 묶음 끝)와 앞 묶음의 마지막 거른 값.
  let pos = 0;
  let prev = 0;

  return {
    push(input: Float32Array): Float32Array {
      if (input.length === 0) return new Float32Array(0);

      let src = input;

      if (filter) {
        const joined = new Float32Array(history.length + input.length);

        joined.set(history);
        joined.set(input, history.length);

        const filtered = new Float32Array(input.length);

        for (let i = 0; i < input.length; i += 1) {
          let acc = 0;

          for (let k = 0; k < TAPS; k += 1) acc += filter[k] * joined[i + k];
          filtered[i] = acc;
        }
        history = joined.slice(joined.length - (TAPS - 1));
        src = filtered;
      }

      const out: number[] = [];

      while (pos < src.length - 1) {
        const i = Math.floor(pos);
        const frac = pos - i;
        const a = i < 0 ? prev : src[i];
        const b = src[i + 1];

        out.push(a + (b - a) * frac);
        pos += step;
      }
      pos -= src.length;
      prev = src[src.length - 1];

      return Float32Array.from(out);
    },
  };
}
