// 상담사 앱(폰) 화면에서만 '홈 화면에 추가' 정보를 문서 머리에 붙인다(public/app/manifest.webmanifest · 아이콘).
// 웹 화면(index.html)에 두면 PC 웹도 설치 대상이 되고 시작 화면이 앱 홈이 되므로, 앱 화면이 붙어 있을 때만 붙이고 떠나면 뗀다.
//  - 안드로이드 Chrome: manifest 로 설치(메뉴 › 홈 화면에 추가 / 앱 설치). 시작 주소 #/AppHome, 주소창 없이 열린다.
//  - iPhone Safari: 공유 › 홈 화면에 추가. apple-mobile-web-app-capable 로 주소창 없이, 지금 화면 주소로 열린다(홈에서 추가하면 홈).
//  - 연결 없이 열기: 서비스워커(public/sw.js)를 등록한다. 화면 파일만 폰에 저장했다가 연결이 없을 때 내준다(API · 아동 앱은 안 건드림).
//    한 번 등록하면 이 폰에서는 웹 화면도 같은 방식(연결되면 늘 새로 받음)으로 열린다.

import { useEffect } from "react";

const TAGS: [string, Record<string, string>][] = [
  ["link", { rel: "manifest", href: "app/manifest.webmanifest" }],
  ["link", { rel: "apple-touch-icon", href: "app/apple-touch-icon.png" }],
  ["meta", { name: "apple-mobile-web-app-capable", content: "yes" }],
  ["meta", { name: "mobile-web-app-capable", content: "yes" }],
  ["meta", { name: "apple-mobile-web-app-title", content: "I-SPOT" }],
  ["meta", { name: "apple-mobile-web-app-status-bar-style", content: "default" }],
  ["meta", { name: "theme-color", content: "#F2F2F0" }],
];

export function useAppInstall(): void {
  useEffect(() => {
    const added = TAGS.map(([tag, attrs]) => {
      const el = document.createElement(tag);

      Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
      el.setAttribute("data-app-install", "");
      document.head.appendChild(el);

      return el;
    });

    try {
      if ("serviceWorker" in navigator && window.isSecureContext) {
        navigator.serviceWorker.register("sw.js", { scope: "./" }).catch(() => {});
      }
    } catch {
      // 안 되는 브라우저면 연결이 있을 때만 열린다
    }

    return () => added.forEach((el) => el.remove());
  }, []);
}
