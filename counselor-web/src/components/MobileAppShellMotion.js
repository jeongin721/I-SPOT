// 상담사 앱(폰) 화면 넘김 · 창 열고 닫기 움직임 — 11/19 디자인(App*.dc.html 의 animIn · animInit · setState 덮어쓰기)을 React 로 옮김.
//  - 화면 넘김: 앱 화면 링크를 누를 때 종류(아래 메뉴 tab · 녹음 rec · 뒤로 back · 그 밖 push)를 적어 두고,
//    새 화면의 틀(MobileAppShell)이 붙을 때 본문 · 제목 · 아래 메뉴 아이콘 · 카드를 움직인다(디자인 값 그대로).
//    디자인은 화면 사이를 localStorage('ispot-app-nav')로 건넸지만 여기는 한 페이지 앱이라 모듈 변수로 건넨다.
//    폰 '뒤로'(브라우저 뒤로 · popstate)도 'back' 으로 본다(디자인에는 없는 경로라 더함).
//  - 창 닫기: 아래 창 · 가운데 창 · 펼친 목록(달력 · 회차 목록)을 0.19초 동안 사라지게 한 뒤 상태를 바꾼다.
//  - 내용 바뀜: 걸러 보기 · 날 · 회차 · 메모 목록이 바뀌면 카드를 차례로 올린다.
//  - 동작 줄이기(prefers-reduced-motion: reduce)면 아무것도 움직이지 않고 바로 상태를 바꾼다.

const EASE = 'cubic-bezier(.22,.9,.3,1)';

/** 움직여도 되는가(동작 줄이기 설정이 아니면 true). */
export function motionOk() {
  try {
    return !(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  } catch {
    return true;
  }
}

/** el 에 Web Animations 를 건다. 못 걸면(없음 · 동작 줄이기) null. */
export function runAnim(el, frames, opt) {
  try {
    if (el && el.animate && motionOk()) return el.animate(frames, opt);
  } catch {
    /* 움직임은 꾸밈이라 실패해도 그냥 둔다 */
  }
  return null;
}

const closing = new WeakSet();

/**
 * 창(.ma-ov) · 펼친 목록(.ma-mcal · .ma-pk-drop)을 사라지게 한 뒤 done() 을 부른다(디자인 setState 덮어쓰기와 같은 값).
 * el 이 없거나 동작 줄이기면 바로 done(). 이미 닫는 중인 el 이면 다시 부르지 않는다.
 */
export function closeWithAnim(el, done) {
  if (!el || !el.animate || !motionOk()) {
    done();
    return;
  }
  if (closing.has(el)) return;
  closing.add(el);
  if (el.classList.contains('ma-ov')) {
    runAnim(el, [{ opacity: 1 }, { opacity: 0 }], { duration: 200, easing: 'ease-in', fill: 'forwards' });
    const sh = el.querySelector('.ma-sheet');
    if (sh)
      runAnim(
        sh,
        sh.classList.contains('ma-sheet-c')
          ? [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'scale(.95)' }]
          : [{ transform: 'none' }, { transform: 'translateY(100%)' }],
        { duration: 200, easing: 'cubic-bezier(.4,0,1,1)', fill: 'forwards' },
      );
  } else {
    runAnim(el, [{ opacity: 1, clipPath: 'inset(0 0 0 0)' }, { opacity: 0, clipPath: 'inset(0 0 100% 0)' }], {
      duration: 220,
      easing: 'cubic-bezier(.4,0,.6,1)',
      fill: 'forwards',
    });
  }
  window.setTimeout(() => {
    closing.delete(el);
    done();
  }, 190);
}

/** 내용이 바뀐 뒤 selector 에 맞는 카드 앞 limit 개를 차례로 올린다(디자인 CH). */
export function staggerIn(selector, limit = 8) {
  window.setTimeout(() => {
    try {
      [...document.querySelectorAll(selector)].slice(0, limit).forEach((c, i) =>
        runAnim(c, [{ opacity: 0, transform: 'translateY(10px)' }, { opacity: 1, transform: 'none' }], {
          duration: 280,
          delay: i * 35,
          easing: EASE,
          fill: 'backwards',
        }),
      );
    } catch {
      /* 꾸밈 */
    }
  }, 20);
}

/** 화면에 들어올 때 움직임(디자인 animIn). */
export function animIn(kind) {
  const d = document;
  const main = d.querySelector('.ma-amain');
  const tl = d.querySelector('.ma-ahd .ma-tl');
  const F = {
    push: [{ opacity: 0, transform: 'translateX(36px)' }, { opacity: 1, transform: 'none' }],
    back: [{ opacity: 0, transform: 'translateX(-36px)' }, { opacity: 1, transform: 'none' }],
    tab: [{ opacity: 0, transform: 'translateY(10px)' }, { opacity: 1, transform: 'none' }],
    rec: [{ opacity: 0, transform: 'translateY(28px) scale(.96)' }, { opacity: 1, transform: 'none' }],
  };
  runAnim(main, F[kind] || F.push, { duration: kind === 'tab' ? 260 : 340, easing: EASE });
  if (kind !== 'tab') runAnim(tl, kind === 'back' ? F.back : F.push, { duration: 300, easing: EASE, delay: 40 });
  if (kind === 'tab' || kind === 'rec')
    runAnim(d.querySelector('.ma-tabs .ma-on .ma-ti'), [{ transform: 'scale(.78)' }, { transform: 'scale(1.1)' }, { transform: 'none' }], {
      duration: 320,
      easing: 'ease-out',
    });
  if (kind !== 'back')
    [...d.querySelectorAll('.ma-amain > .ma-card')].slice(0, 6).forEach((c, i) =>
      runAnim(c, [{ opacity: 0, transform: 'translateY(12px)' }, { opacity: 1, transform: 'none' }], {
        duration: 300,
        delay: 60 + i * 40,
        easing: EASE,
        fill: 'backwards',
      }),
    );
}

// 앞 화면에서 누른 이동(어느 화면으로 · 어떤 종류 · 언제). 새 화면의 틀이 붙을 때 읽고 지운다.
let pendingNav = null;

const APP_PATH = /^\/App[A-Za-z]+$/;

/** 링크 href('#/AppHistory?case=…', HashRouter) · 주소 해시에서 화면 경로('/AppHistory')만. */
function routeOf(href) {
  const h = String(href || '');
  const i = h.indexOf('#');
  return (i >= 0 ? h.slice(i + 1) : h).split(/[?#]/)[0];
}

/** 앞 화면에서 적어 둔 이동이 이 화면 것이면 꺼낸다(2.5초 안). */
export function takeNav(pathname) {
  const n = pendingNav;
  pendingNav = null;
  return n && n.to === pathname && Date.now() - n.t < 2500 ? n : null;
}

/** 문서 전체 클릭(잡기 단계) · 뒤로 가기를 듣는다. 돌려준 함수로 그만 듣는다(디자인 animInit). */
export function listenNav(pathname) {
  const onClick = (ev) => {
    const a = ev.target && ev.target.closest ? ev.target.closest('a[href]') : null;
    if (!a) return;
    const path = routeOf(a.getAttribute('href'));
    if (!APP_PATH.test(path) || path === pathname) return;
    const kind = a.closest('.ma-tabs')
      ? a.classList.contains('ma-tab-rec')
        ? 'rec'
        : 'tab'
      : a.getAttribute('aria-label') === '뒤로 가기'
        ? 'back'
        : 'push';
    pendingNav = { to: path, kind, t: Date.now() };
    runAnim(a, [{ transform: 'scale(.95)' }, { transform: 'none' }], { duration: 180, easing: 'ease-out' });
  };
  const onPop = () => {
    pendingNav = { to: routeOf(window.location.hash), kind: 'back', t: Date.now() };
  };
  document.addEventListener('click', onClick, true);
  window.addEventListener('popstate', onPop);
  return () => {
    document.removeEventListener('click', onClick, true);
    window.removeEventListener('popstate', onPop);
  };
}
