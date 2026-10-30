// 서식 4 ② 의 가족관계 표 · 건강정도 표(10/29 디자인 ftg · hs-*). 새 사례 등록 · 초기면접지가 같이 쓴다.
// 값은 data/screens/personalFields.ts(personalFieldValues)의 family · health 를 그대로 받는다.
// 건강정도는 서버가 항목마다 '유 · 무' 와 세부 글 한 칸만 받아, 디자인의 세부 칸(횟수 · 기간 등)을 세부 글 한 칸으로 합쳤다.
import { Fragment } from 'react';

export function FamilyTable({ family }) {
  return (
    <>
      <div style={{ overflowX: 'auto' }}>
        <table className="ft ftg">
          <thead>
            <tr>
              {family.columns.map((label) => (
                <th key={label}>{label}</th>
              ))}
              <th>동거여부</th>
              <th style={{ width: '56px' }} aria-label="줄 빼기"></th>
            </tr>
          </thead>
          <tbody>
            {family.rows.map((r, rIndex) => (
              <tr key={rIndex}>
                {r.cells.map((c) => (
                  <td key={c.label}>
                    <input
                      aria-label={`${rIndex + 1}번째 줄 ${c.label}`}
                      value={c.value}
                      inputMode={c.numeric ? 'numeric' : undefined}
                      onChange={c.onChange}
                      disabled={family.locked}
                    />
                  </td>
                ))}
                <td>
                  <select
                    className="ft-sel"
                    aria-label={`${rIndex + 1}번째 줄 동거여부`}
                    value={r.living.value}
                    onChange={r.living.onChange}
                    disabled={family.locked}
                  >
                    <option value="">선택</option>
                    <option value="동거">동거</option>
                    <option value="비동거">비동거</option>
                  </select>
                </td>
                <td style={{ textAlign: 'center' }}>
                  <button
                    type="button"
                    className="ft-del"
                    aria-label={`${rIndex + 1}번째 줄 빼기`}
                    onClick={r.remove}
                    disabled={family.locked}
                  >
                    ×
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button
        type="button"
        className="btn btn-sm btn-s"
        style={{ alignSelf: 'flex-start' }}
        onClick={family.add}
        disabled={!family.canAdd}
      >
        + 가족 추가
      </button>
    </>
  );
}

export function HealthTable({ health }) {
  return (
    <>
      <div className="sec hs-sec">
        <span aria-hidden="true">(</span>
        <input
          className="hs-name"
          type="text"
          placeholder="이름"
          aria-label="건강정도 대상자 이름"
          value={health.subject.value}
          onChange={health.subject.onChange}
          disabled={health.locked}
        />
        <span aria-hidden="true">)</span>건강정도
      </div>
      <p className="note" style={{ margin: '-8px 0 0' }}>
        *피해아동, 사례관리대상자, 가족구성원 중 해당하는 사람에 대해 기재 · 횟수 · 기간 등은 세부 칸에 함께 적습니다
      </p>
      <div className="hs-tbl">
        {health.rows.map((row) => (
          <div className="hs-row" key={row.kind}>
            <span className="hs-k">{row.kind}</span>
            <div className="hs-v">
              {row.pickers.map((o) => (
                <Fragment key={o.label}>
                  <button
                    type="button"
                    className="pk hs-pk"
                    aria-pressed={o.on}
                    onClick={o.pick}
                    disabled={health.locked}
                    style={{ background: o.bg, borderColor: o.bd, color: o.fg, fontWeight: o.fw }}
                  >
                    {o.label}
                  </button>
                </Fragment>
              ))}
              <input
                className="hs-in hs-w hs-wide"
                type="text"
                aria-label={`${row.kind} 세부 내용`}
                placeholder={row.detail.placeholder}
                value={row.detail.value}
                onChange={row.detail.onChange}
                disabled={health.locked}
              />
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
