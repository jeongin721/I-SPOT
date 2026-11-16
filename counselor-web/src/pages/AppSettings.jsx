// 상담사 앱(폰) · 설정
// 원본: 앱 · 설정 (내 정보 · 어두운 화면 · 알림 · 업로드) 2026-11-10 zip 의 AppSettings.dc.html
//
// 서버 연결
//  - 내 정보: 로그인한 상담사 이름 · 이메일(GET /auth/me). 소속 기관은 서버에 없어 '—'.
//  - 어두운 화면: 웹과 같은 설정(useTheme, 이 브라우저에 기억). 켜면 웹 화면도 어둡게 바뀐다.
//  - 알림 3개 · Wi-Fi에서만 올리기: 폰 알림(푸시) · 연결 종류를 아는 기능이 아직 없어 흐린 '준비 중' 스위치로 둔다(누를 수 없음).
//    업로드 실패는 앱 안의 알림(종)에 늘 보인다.
//  - 로그아웃: 웹과 같은 로그아웃. 폰에 기억한 계정 · 사례 목록도 지운다(client.clearToken).
//    올리지 못한 녹음 · 메모는 남는다(같은 계정으로 다시 로그인하면 보인다).
import { useNavigate } from 'react-router-dom';
import MobileAppShell from '../components/MobileAppShell';
import { useTheme } from '../theme';

function Toggle({ label, on, onClick, off }) {
  return (
    <div className="ma-sr">
      <span className="ma-st">
        <b style={{ fontWeight: 500 }}>{label}</b>
        {off && <span className="ma-note">준비 중</span>}
      </span>
      <button
        type="button"
        className={'ma-tg' + (on ? ' ma-on' : '') + (off ? ' ma-off' : '')}
        role="switch"
        aria-checked={on ? 'true' : 'false'}
        aria-label={label}
        aria-disabled={off ? 'true' : undefined}
        onClick={off ? undefined : onClick}
      ></button>
    </div>
  );
}

function SettingsBody({ me, logout }) {
  const theme = useTheme();
  const navigate = useNavigate();
  const name = me?.name ?? '';

  return (
    <>
      <section className="ma-card ma-prof" aria-label="내 정보">
        <span className="ma-av">{name ? name.slice(0, 1) : '—'}</span>
        <span style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '2px' }}>
          <b style={{ fontSize: '17px' }}>{name ? `${name} 상담원` : '—'}</b>
          <span className="ma-note">소속 기관 —</span>
          <span className="ma-note" style={{ overflowWrap: 'anywhere' }}>
            {me?.email ?? '—'}
          </span>
        </span>
      </section>
      <p className="ma-sec-t">화면</p>
      <section className="ma-card ma-grp">
        <Toggle label="어두운 화면" on={theme.dark} onClick={theme.toggle} />
      </section>
      <p className="ma-sec-t">알림</p>
      <section className="ma-card ma-grp">
        <Toggle label="알림 받기" on={false} off />
        <Toggle label="업로드 실패 알림" on={false} off />
        <Toggle label="상담 30분 전 알림" on={false} off />
      </section>
      <p className="ma-sec-t">업로드</p>
      <section className="ma-card ma-grp">
        <Toggle label="Wi-Fi에서만 올리기" on={false} off />
      </section>
      <p className="ma-sec-t">앱 정보</p>
      <section className="ma-card ma-grp">
        <div className="ma-sr">
          <span className="ma-st">버전</span>
          <span className="ma-note">1.0.0</span>
        </div>
        <div className="ma-sr">
          <span className="ma-st">계정 정보 변경</span>
          <span className="ma-note">웹 설정에서 설정 가능</span>
        </div>
      </section>
      <button
        type="button"
        className="ma-btn ma-btn-block ma-btn-red"
        onClick={() => {
          logout();
          navigate('/Login', { replace: true });
        }}
      >
        로그아웃
      </button>
    </>
  );
}

export default function AppSettings() {
  return (
    <MobileAppShell cur="set" screen="set" sub="계정 · 알림 · 앱" title="설정">
      {(ctx) => <SettingsBody {...ctx} />}
    </MobileAppShell>
  );
}
