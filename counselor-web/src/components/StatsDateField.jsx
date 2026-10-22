// 통계 화면의 기간 칸 하나(시작일 · 종료일): YYYY-MM-DD 글자 입력 + 달력 단추 + 연 → 월 → 일 팝업.
// 원본: 10/21 디자인 counselor-design/screens/Stats.dc.html 의 날짜 칸(.dpw · .dp-*, dpBuild).
//
// 값과 동작(입력 초안 · 검증 · 팝업 단계 · 고를 수 있는 날)은 src/data/screens/stats.ts 의 fromField · toField 가 만들고,
// 이 파일은 배치와 브라우저 쪽 일만 한다.
//  - 연도 목록 굴리기: 디자인은 id + setTimeout + componentDidUpdate 로 했지만 앱 useDC 는 componentDidUpdate 를 부르지 않아
//    목록 ref 와 useEffect 로 고른 해가 보이게 굴린다.
//  - 닫기: 팝업 밖(투명 배경)을 누르거나 Esc. Esc · 날짜를 고른 뒤에는 달력 단추로 초점을 돌린다.
//  - 팝업을 열거나 연 → 월 → 일로 넘어가면 누른 단추가 사라져 초점이 문서 처음으로 가므로, 그 단계의 고른 단추
//    (없으면 고를 수 있는 첫 단추)로 옮긴다.
//  - 모양 규칙은 src/pages/Stats.css(.pg-Stats .dpw · .dp-*)에 있다.
import { Fragment, useEffect, useId, useRef } from 'react';

export default function StatsDateField({ label, name, field }) {
  const id = useId();
  const yearsRef = useRef(null);
  const btnRef = useRef(null);
  const popRef = useRef(null);
  const dp = field.picker;
  const { open, close, scrollKey } = dp;
  const mode = !open ? '' : dp.isY ? 'y' : dp.isM ? 'm' : 'd';

  useEffect(() => {
    const pop = popRef.current;
    if (!mode || !pop || pop.contains(document.activeElement)) return;
    const target = pop.querySelector(`.dp-${mode}.on:not(:disabled)`) ?? pop.querySelector(`.dp-${mode}:not(:disabled)`);
    if (target) target.focus();
  }, [mode]);

  // 연도 목록이 보이면 고른 해가 목록 위쪽에서 조금 내려온 자리에 오게 굴린다.
  useEffect(() => {
    const box = yearsRef.current;
    if (!box || !scrollKey) return;
    const on = box.querySelector('.dp-y.on');
    if (on) box.scrollTop += on.getBoundingClientRect().top - box.getBoundingClientRect().top - 80;
  }, [scrollKey]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key !== 'Escape') return;
      close();
      if (btnRef.current) btnRef.current.focus();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, close]);

  const pickDay = (d) => {
    d.pick();
    if (btnRef.current) btnRef.current.focus();
  };

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
      <label className="note" htmlFor={id}>
        {label}
      </label>
      <span className="dpw st">
        <input
          id={id}
          className="inp dpi"
          type="text"
          inputMode="numeric"
          placeholder="YYYY-MM-DD"
          maxLength={10}
          value={field.value}
          onChange={field.onChange}
          onBlur={field.onBlur}
          aria-label={name}
        />
        <button
          ref={btnRef}
          type="button"
          className="dp-btn"
          aria-label={`${name} 달력 열기`}
          aria-expanded={open}
          onClick={dp.toggle}
        >
          <svg
            viewBox="0 0 24 24"
            width="17"
            height="17"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <rect x="3" y="5" width="18" height="16" rx="2"></rect>
            <path d="M16 3v4M8 3v4M3 10h18"></path>
          </svg>
        </button>
        {open ? (
          <>
            <span className="dp-bd" onClick={close}></span>
            <span className="dp-pop" role="dialog" aria-label={`${name} 선택`} ref={popRef}>
              {dp.isY ? (
                <>
                  <span className="dp-hd">
                    <b>연도 선택</b>
                  </span>
                  <span className="dp-years" ref={yearsRef}>
                    {dp.years.map((o) => (
                      <button
                        key={o.label}
                        type="button"
                        className={`dp-y ${o.cls}`}
                        aria-pressed={o.on}
                        onClick={o.pick}
                      >
                        {o.label}
                      </button>
                    ))}
                  </span>
                </>
              ) : null}
              {dp.isM ? (
                <>
                  <span className="dp-hd">
                    <button type="button" className="dp-nav" aria-label="연도 선택으로" onClick={dp.toY}>
                      ←
                    </button>
                    <b>{dp.yLabel}</b>
                  </span>
                  <span className="dp-months">
                    {dp.months.map((o) => (
                      <button
                        key={o.label}
                        type="button"
                        className={`dp-m ${o.cls}`}
                        disabled={o.dis}
                        onClick={o.pick}
                      >
                        {o.label}
                      </button>
                    ))}
                  </span>
                </>
              ) : null}
              {dp.isD ? (
                <>
                  <span className="dp-hd">
                    <button type="button" className="dp-nav" aria-label="월 선택으로" onClick={dp.toM}>
                      ←
                    </button>
                    <b>{dp.ymLabel}</b>
                    <span style={{ marginLeft: 'auto', display: 'inline-flex', gap: '6px' }}>
                      <button
                        type="button"
                        className="dp-nav"
                        aria-label="이전 달"
                        disabled={dp.prevDis}
                        onClick={dp.prev}
                      >
                        ‹
                      </button>
                      <button
                        type="button"
                        className="dp-nav"
                        aria-label="다음 달"
                        disabled={dp.nextDis}
                        onClick={dp.next}
                      >
                        ›
                      </button>
                    </span>
                  </span>
                  <span className="dp-days">
                    {dp.dows.map((w) => (
                      <span key={w} className="dp-dow">
                        {w}
                      </span>
                    ))}
                    {dp.days.map((o, oIndex) => (
                      <Fragment key={oIndex}>
                        {o.blank ? (
                          <span></span>
                        ) : (
                          <button
                            type="button"
                            className={`dp-d ${o.cls}`}
                            disabled={o.dis}
                            aria-label={o.aria}
                            onClick={() => pickDay(o)}
                          >
                            {o.n}
                          </button>
                        )}
                      </Fragment>
                    ))}
                  </span>
                </>
              ) : null}
            </span>
          </>
        ) : null}
      </span>
    </span>
  );
}
