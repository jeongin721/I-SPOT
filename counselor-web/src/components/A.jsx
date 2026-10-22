// 화면 간 이동 링크. '/CaseDetail' 같은 내부 경로는 react-router Link 로, 그 밖은 일반 <a> 로 그려요.
// 팝업(녹취 올리기 · 새 사례 등록)으로 가는 링크에는 지금 화면 주소를 back 쿼리로 붙여, 닫으면 이 화면으로 돌아오게 해요
// (src/data/screens/links.ts 의 withBack). 팝업 안에서 다른 팝업으로 갈 때는 붙이지 않아요.
import { Link, useLocation } from 'react-router-dom';
import { POPUP_PAGES, withBack } from '../data/screens/links';

export default function A({ to, href, children, ...rest }) {
  const location = useLocation();
  const target = to ?? href ?? '';
  if (typeof target === 'string' && target.startsWith('/')) {
    const toPopup = POPUP_PAGES.has(target.split('?')[0]) && !POPUP_PAGES.has(location.pathname);
    return (
      <Link to={toPopup ? withBack(target, location.pathname + location.search) : target} {...rest}>
        {children}
      </Link>
    );
  }
  return (
    <a href={target} {...rest}>
      {children}
    </a>
  );
}
