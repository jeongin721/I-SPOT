// 회차 처리 화면 위의 단계 표시(1 STT 검수 · 2 유형별 위험도 · 3 요약 · 일지 작성 · 4 추가 확인 · 질문).
// 값은 src/data/screens/flow.ts 의 processNav 가 만든다(processHeaderValues 의 steps).
// 끝난 단계(✓)와 지금 할 단계만 링크로 그린다. 지금 화면(현재 단계)과 아직 열리지 않은 뒤 단계는 링크가 아니라 눌러도
// 옮기지 않는다 — 다음 단계로는 화면 아래 단추('원문 확정 · 유형별 위험도 →' 같은)로만 간다(10/27).
import { Fragment } from 'react';
import A from './A';

export default function StepNav({ steps }) {
  return (
    <nav className="steps" aria-label="회차 처리 단계">
      {(steps || []).map((t, i) => {
        const body = (
          <Fragment>
            <span className="sn">{t.mark}</span>
            <b style={{ fontWeight: t.weight }}>{t.label}</b>
          </Fragment>
        );

        if (t.href) {
          return (
            <A key={i} className={t.cls} to={t.href}>
              {body}
            </A>
          );
        }

        return (
          <span
            key={i}
            className={t.cls}
            aria-current={t.current}
            aria-disabled={t.current ? undefined : 'true'}
            title={t.title}
          >
            {body}
          </span>
        );
      })}
    </nav>
  );
}
