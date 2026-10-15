// 여러 요청을 한꺼번에 다 보내지 않고 limit 개씩 나눠 부른다(문서함 · 통계 · 일정처럼 사례 · 회차마다 부르는 훅).

/** items 를 limit 개씩 나눠 차례로 부른다. 결과 순서는 items 와 같다. 하나라도 실패하면 그 오류로 끝난다. */
export async function mapLimited<T, R>(items: T[], limit: number, run: (item: T) => Promise<R>): Promise<R[]> {
  const results: R[] = new Array(items.length);
  let next = 0;

  async function worker() {
    while (next < items.length) {
      const index = next++;
      results[index] = await run(items[index]);
    }
  }

  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));

  return results;
}
