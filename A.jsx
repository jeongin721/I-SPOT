// 화면 간 이동 링크. '/CaseDetail' 같은 내부 경로는 react-router Link 로, 그 밖은 일반 <a> 로 그려요.
import { Link } from 'react-router-dom';

export default function A({ to, href, children, ...rest }) {
  const target = to ?? href ?? '';
  if (typeof target === 'string' && target.startsWith('/')) {
    return (
      <Link to={target} {...rest}>
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
