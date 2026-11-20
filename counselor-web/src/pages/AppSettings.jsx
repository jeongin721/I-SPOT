// 상담사 앱(폰) · 설정
// 원본: 앱 · 설정 (내 정보 · 어두운 화면 · 알림 · 업로드) 2026-11-10 zip 의 AppSettings.dc.html
//
// 서버 연결
//  - 내 정보: 로그인한 상담사 이름 · 이메일(GET /auth/me). 소속 기관은 서버에 없어 '—'.
//  - 어두운 화면: 웹과 같은 설정(useTheme, 이 브라우저에 기억). 켜면 웹 화면도 어둡게 바뀐다.
//  - 알림 3개(2026-11-19, API_CONTRACT 27절 · data/appPush): '알림 받기' 를 켜면 폰 알림 허락 → 푸시 구독 → 서버 저장 → 시험 알림.
//    '상담 30분 전 알림' 은 서버가, '업로드 실패 알림' 은 폰이 스스로 띄운다. 둘은 알림 받기가 켜져 있을 때만 누를 수 있다.
//    서버에 키가 없으면 '준비 중', 이 브라우저가 못 하면(iPhone 은 홈 화면에 추가한 앱에서만 됨) '홈 화면 앱에서' 를 보인다.
//    업로드 실패는 앱 안의 알림(종)에도 늘 보인다.
//  - Wi-Fi에서만 올리기: 연결 종류를 아는 기능이 아직 없어 흐린 '준비 중' 스위치로 둔다(누를 수 없음).
//  - 로그아웃: 이 폰의 알림을 먼저 끈다(다음 사람이 앞 사람 알림을 받지 않게). 그다음 웹과 같은 로그아웃. 폰에 기억한 계정 · 사례 목록도 지운다(client.clearToken).
//    올리지 못한 녹음 · 메모는 남는다(같은 계정으로 다시 로그인하면 보인다).
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { push } from '../api/endpoints';
import { disablePush, enablePush, pushSupported, readPushPrefs, setPushPref, syncPush } from '../data/appPush';
import MobileAppShell from '../components/MobileAppShell';
import { useTheme } from '../theme';

function Toggle({ label, on, onClick, off, note }) {
  // note 를 주지 않으면 누를 수 없는 스위치에 '준비 중'.
  const shown = note !== undefined ? note : off ? '준비 중' : null;

  return (
    <div className="ma-sr">
      <span className="ma-st">
        <b style={{ fontWeight: 500 }}>{label}</b>
        {shown && <span className="ma-note">{shown}</span>}
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

const ENABLE_NOTE = {
  denied: '폰 설정에서 이 앱의 알림을 허용해 주세요',
  unsupported: '홈 화면에 추가한 앱에서 켤 수 있어요',
  disabled: '준비 중',
};

/** 알림 스위치 상태. ready: 서버 키 있음(null 이면 아직 모름). note: 알림 받기 옆에 보일 안내. */
function usePushSettings() {
  const [prefs, setPrefs] = useState(readPushPrefs);
  const [ready, setReady] = useState(null);
  // 상담 전 알림을 서버가 실제로 보내는가 · 몇 분 전인가(GET /push/config). 연결이 안 되면 offline.
  const [loop, setLoop] = useState({ on: null, minutes: 30 });
  const [offline, setOffline] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null);

  useEffect(() => {
    let live = true;

    push
      .config()
      .then((config) => {
        if (!live) return;
        setReady(config.enabled);
        setLoop({ on: config.before_session_enabled ?? config.enabled, minutes: config.before_session_minutes || 30 });
      })
      .catch(() => live && setOffline(true));
    syncPush()
      .then((on) => live && setPrefs({ ...readPushPrefs(), on }))
      .catch(() => undefined);

    return () => {
      live = false;
    };
  }, []);

  const toggleOn = async () => {
    if (busy) return;
    setBusy(true);
    setNote(null);
    try {
      if (prefs.on) {
        await disablePush();
      } else {
        const result = await enablePush();
        if (result !== 'ok') setNote(ENABLE_NOTE[result]);
        if (result === 'disabled') setReady(false);
      }
    } catch {
      setNote('알림을 켜지 못했어요. 잠시 뒤 다시 눌러 주세요');
    } finally {
      setPrefs(readPushPrefs());
      setBusy(false);
    }
  };

  const toggle = (name) => async () => {
    setPrefs({ ...prefs, [name]: !prefs[name] });
    await setPushPref(name, !prefs[name]).catch(() => undefined);
    setPrefs(readPushPrefs());
  };

  const supported = pushSupported();
  // 서버 키가 없으면 '준비 중'. 이 브라우저가 못 하면 켤 때 안내한다(누르기 전에도 보인다).
  const masterOff = ready === false;
  const masterNote = masterOff
    ? '준비 중'
    : note ?? (offline && ready === null ? '연결을 확인해 주세요' : supported ? null : ENABLE_NOTE.unsupported);
  // 키는 있어도 상담 전 알림 발송이 꺼져 있으면 그 스위치만 '준비 중'.
  const loopOff = masterOff || loop.on === false;

  return { prefs, busy, masterOff, masterNote, toggleOn, toggle, loopOff, minutes: loop.minutes };
}

function SettingsBody({ me, logout }) {
  const theme = useTheme();
  const navigate = useNavigate();
  const name = me?.name ?? '';
  const pushUi = usePushSettings();
  const subOff = pushUi.masterOff || !pushUi.prefs.on;

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
        <Toggle label="알림 받기" on={pushUi.prefs.on && !pushUi.masterOff} onClick={pushUi.toggleOn} off={pushUi.masterOff} note={pushUi.masterNote} />
        <Toggle
          label="업로드 실패 알림"
          on={!subOff && pushUi.prefs.upload_failed}
          onClick={pushUi.toggle('upload_failed')}
          off={subOff}
          note={pushUi.masterOff ? '준비 중' : null}
        />
        <Toggle
          label={`상담 ${pushUi.minutes}분 전 알림`}
          on={!subOff && !pushUi.loopOff && pushUi.prefs.before_session}
          onClick={pushUi.toggle('before_session')}
          off={subOff || pushUi.loopOff}
          note={pushUi.loopOff ? '준비 중' : null}
        />
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
        onClick={async () => {
          // 알림 끄기는 기다리되 오래 걸리면(연결 없음) 그냥 로그아웃한다.
          await Promise.race([disablePush().catch(() => undefined), new Promise((resolve) => setTimeout(resolve, 3000))]);
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
