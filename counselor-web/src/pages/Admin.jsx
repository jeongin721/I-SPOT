// 옛 관리자 주소(#/Admin, #/Admin?view=tasks · accounts · audit)를 새 관리자 화면으로 옮긴다.
// 10/21 새 디자인은 관리자 화면을 여러 장으로 나눴다(AdminHome · AdminAccounts · AdminSecurity · AdminStats · AdminStaffDetail).
// 앱의 업무 처리 현황 보기는 AdminTasks 로 옮겼다. 로그인 화면 · 상담원 메뉴의 '관리자 메뉴' 링크가 아직 #/Admin 을 가리켜서 남겨 둔다.
// 관리자인지는 옮긴 화면이 본다(관리자가 아니면 안내만 보이고 서버는 부르지 않는다).
import { Navigate, useSearchParams } from 'react-router-dom';
import { adminRedirectHref } from '../data/screens/admin';

export default function Admin() {
  const [search] = useSearchParams();
  return <Navigate to={adminRedirectHref(search)} replace />;
}
