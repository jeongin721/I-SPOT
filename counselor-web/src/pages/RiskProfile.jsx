// 옛 '유형별 위험도' 주소(#/RiskProfile?case=…&session=…)를 2 · 유형별 위험도(SignalReview)로 옮긴다.
// 10/27 디자인은 '위험 신호 검토' 와 '유형별 위험도' 를 한 화면(SignalReview.dc.html)으로 합쳤다.
// 예전에 저장해 둔 링크 · 브라우저 기록이 깨지지 않게 남겨 둔다. 사례 · 회차 ID 는 그대로 넘긴다.
import { Navigate, useSearchParams } from 'react-router-dom';
import { readScreenIds, screenHref } from '../data/screens/links';

export default function RiskProfile() {
  const ids = readScreenIds(useSearchParams()[0]);
  return <Navigate to={screenHref('/SignalReview', ids)} replace />;
}
