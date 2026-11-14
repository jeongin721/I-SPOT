// 상담사 앱(폰) · 메모
// 원본: 앱 · 메모 (작성 · 수정 · 삭제) 2026-11-10 zip 의 AppMemo.dc.html
//
// 메모는 서버에 저장한다(민규 #169 — 폰에만 저장하는 판을 먼저 넣으면 나중에 폰에 쌓인 메모를 서버로 옮겨야 한다).
// 메모 API 가 들어오기 전까지 이 화면은 '준비 중' 이다. 작성 · 수정 · 삭제 화면은 메모 API PR 에서 함께 넣는다.
import MobileAppShell from '../components/MobileAppShell';

export default function AppMemo() {
  return (
    <MobileAppShell cur="memo" screen="memo" sub="현장에서 바로 적어 두기" title="메모">
      {() => (
        <div className="ma-card" style={{ padding: '28px 16px', textAlign: 'center', color: 'var(--mut)', fontSize: '14px' }}>
          메모는 준비 중이에요
        </div>
      )}
    </MobileAppShell>
  );
}
