// 내담자 정보 › '사례 한눈에 보기'(2026-11-13). 값은 data/screens/caseOverview.ts — 이 파일은 배치만 한다.
// 디자인에 없던 칸이라 기존 카드(.card · .kv · .chip)만 쓴다.
import { Fragment } from 'react';
import A from './A';

export default function CaseOverviewCard({ value }) {
  if (!value || !value.ready) return null;
  return (
    <section className="card" aria-label="사례 한눈에 보기" style={{ padding: '22px 24px' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
        <h2 className="h2">사례 한눈에 보기</h2>
        <span className="note">처음 보는 분을 위한 정리 · 저장된 기록을 모은 것이고 판단은 담당 상담사가 합니다</span>
        <span style={{ marginLeft: 'auto', display: 'flex', gap: '12px', fontSize: '13px' }}>
          {value.intakeHref ? <A to={value.intakeHref}>초기면접지</A> : null}
          {value.historyHref ? <A to={value.historyHref}>상담 이력</A> : null}
        </span>
      </div>
      <dl className="kv" style={{ gridTemplateColumns: '120px minmax(0, 1fr)' }}>
        {value.rows.map((r) => (
          <Fragment key={r.label}>
            <dt>{r.label}</dt>
            <dd>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '6px' }}>
                {r.chips.map((c) => (
                  <span key={c.text} className={c.cls}>
                    {c.text}
                  </span>
                ))}
                {r.text ? <span>{r.text}</span> : null}
                {r.empty ? <span className="note">아직 없음</span> : null}
                {r.ai ? (
                  <span className="chip c-ai" style={{ height: '20px', fontSize: '11px' }}>
                    AI 제안
                  </span>
                ) : null}
              </div>
              <div className="note" style={{ fontSize: '12px' }}>
                {r.source}
              </div>
            </dd>
          </Fragment>
        ))}
      </dl>
    </section>
  );
}
