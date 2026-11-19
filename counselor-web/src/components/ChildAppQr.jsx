// 아이 앱 주소 · 연결 코드 QR(11/19). 연결 코드 화면(아이 상세 · 사례 아이 연계 탭)에서 아이에게 보여 준다.
// QR 에는 아이 앱 주소 + ?code= 를 넣는다 — 찍으면 아이 앱이 코드 칸을 채우고 주소창에서 지운다(public/child-app/index.html).
// 코드는 72시간 · 한 번만 쓸 수 있고, 연결되면 더 쓸 수 없다. QR 은 qrcode-generator 로 이 화면에서 그린다(서버 · 외부로 보내지 않음).
import qrcode from 'qrcode-generator';
import { childAppLinkUrl, childAppUrlLabel } from '../data/childAppUrl';

function QrSvg({ text, size = 148 }) {
  const qr = qrcode(0, 'M');
  qr.addData(text);
  qr.make();
  const n = qr.getModuleCount();
  const margin = 2;
  let d = '';
  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      if (qr.isDark(r, c)) d += `M${c + margin} ${r + margin}h1v1h-1z`;
    }
  }
  const box = n + margin * 2;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${box} ${box}`} role="img" aria-label="아이 앱 연결 QR" shapeRendering="crispEdges">
      <rect width={box} height={box} fill="#FFFFFF" />
      <path d={d} fill="#2B2A26" />
    </svg>
  );
}

export default function ChildAppQr({ code }) {
  const label = childAppUrlLabel();
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '14px 18px' }}>
      {code ? (
        <div style={{ padding: '6px', background: '#FFFFFF', border: '1px solid #E2DED3', borderRadius: '10px', lineHeight: 0 }}>
          <QrSvg text={childAppLinkUrl(code)} />
        </div>
      ) : null}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', minWidth: '200px' }}>
        <span className="sub">아이 앱 주소</span>
        <b style={{ fontSize: '15px', wordBreak: 'break-all' }}>{label}</b>
        <span className="note">
          {code
            ? '아이 폰 카메라로 QR 을 찍으면 콩콩이 열리고 코드가 채워져요. 주소를 직접 열어 코드를 넣어도 돼요.'
            : '아이 폰에서 이 주소를 열고 연결 코드를 넣게 해 주세요.'}
        </span>
      </div>
    </div>
  );
}
