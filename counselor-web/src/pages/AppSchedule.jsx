// 상담사 앱(폰) · 일정
// 원본: 앱 · 일정 (펼치기 → 월간 달력 · 오늘 상담 → 브리핑 · 녹음 일정 추가 · 수정 · 삭제) 2026-11-10 zip 의 AppSchedule.dc.html
//
// 서버 연결: 웹 일정과 같은 일정(GET · POST · PATCH · DELETE /schedule/events). 웹에서 넣은 일정이 그대로 보이고, 여기서 넣은 것도 웹에 보인다.
//  - 이번 주 줄 · 펼친 월간 달력: 고른 날이 든 달(달력 6주)을 한 번에 받아 점(일정 있음)을 찍는다.
//  - 상담 일정: '아이 · 상담 유형', 상담 전 브리핑(앱 · 브리핑) · 녹음 시작(앱 · 녹음)으로 그 아이를 골라 둔 채 간다.
//    사례가 가려진 상담(담당이 바뀐 사례 등)은 두 단추 대신 '브리핑 준비 중' 처럼 흐리게.
//  - 개인 · 기관 일정: 제목(없으면 분류 이름). 폰에서 새로 넣으면 분류는 '기타'(웹에서 바꿀 수 있다). 고칠 때는 원래 분류를 둔다.
//  - 수정 · 삭제는 만든 사람만(editable). 팀 공유 일정 중 남의 것은 보기만.
//  - 날짜 고르기는 디자인처럼 그 주 7일(고치는 일정이 다른 주면 그 날도 넣는다). 다른 주는 달력에서 날을 고른 뒤 추가한다.
//  - 디자인 상세의 '브리핑 준비됨 · 준비 중' 줄은 준비 여부를 정할 서버 값이 없어 넣지 않았다.
import { useState } from 'react';
import { Link } from 'react-router-dom';
import MobileAppShell from '../components/MobileAppShell';
import { schedule } from '../api/endpoints';
import { SCHEDULE_CATEGORY_LABELS, SCHEDULE_CONSULT_LABELS } from '../api/types';
import { childLabelOf, useAppCases } from '../data/useAppCases';
import { addDays, mondayOf, parseYmd, useAppSchedule, ymd } from '../data/useAppSchedule';
import { errorMessage } from '../data/useRemote';

const DOW = ['월', '화', '수', '목', '금', '토', '일'];
const KINDS = [
  ['REGULAR', '정기상담'],
  ['VISIT', '방문상담'],
  ['PHONE', '전화상담'],
  ['INITIAL', '초기면담'],
];

const dowOf = (d) => DOW[(d.getDay() + 6) % 7];
const label = (d) => `${d.getMonth() + 1}월 ${d.getDate()}일 ${dowOf(d)}요일`;

function titleOf(e, names) {
  if (e.kind === 'CONSULT') {
    const who = (e.case_id && names[e.case_id]) || e.child_alias || '아이';
    return `${who} · ${e.consult_type ? SCHEDULE_CONSULT_LABELS[e.consult_type] : '상담'}`;
  }
  return e.title || (e.category ? SCHEDULE_CATEGORY_LABELS[e.category] : '일정');
}

function ScheduleBody({ userId }) {
  const todayD = new Date();
  const today = ymd(todayD);
  const [day, setDay] = useState(today);
  const [exp, setExp] = useState(false);
  const [sheet, setSheet] = useState(null);
  const [ask, setAsk] = useState(false);
  const [f, setF] = useState({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const my = useAppCases(userId);
  const names = Object.fromEntries(my.rows.map((r) => [r.id, childLabelOf(r)]));

  const dayD = parseYmd(day);
  const monthFirst = new Date(dayD.getFullYear(), dayD.getMonth(), 1);
  const gridStart = mondayOf(monthFirst);
  const gridEnd = addDays(gridStart, 41);
  const sched = useAppSchedule(!!userId, ymd(gridStart), ymd(gridEnd));
  const has = (d) => sched.items.some((e) => e.date === d);

  const weekStart = mondayOf(dayD);
  const days = DOW.map((dow, k) => {
    const d = addDays(weekStart, k);
    const key = ymd(d);
    return { key, dow, n: d.getDate(), sel: key === day, today: key === today, dot: has(key) };
  });
  const lastRow = ymd(addDays(gridStart, 35)) > ymd(new Date(dayD.getFullYear(), dayD.getMonth() + 1, 0)) ? 35 : 42;
  const cells = Array.from({ length: lastRow }, (_, i) => {
    const d = addDays(gridStart, i);
    const key = ymd(d);
    return { key, n: d.getDate(), out: d.getMonth() !== dayD.getMonth(), sel: key === day, today: key === today, dot: has(key) };
  });
  const evs = sched.items.filter((e) => e.date === day);
  const cur = sheet?.id ? sched.items.find((e) => e.id === sheet.id) : null;
  const stop = (ev) => ev.stopPropagation();
  const close = () => {
    setSheet(null);
    setAsk(false);
    setErr('');
  };

  const openAdd = () => {
    setErr('');
    setF({ t: 'c', caseId: my.rows[0]?.id ?? '', ctype: 'REGULAR', title: '', day, time: '10:00', place: '' });
    setSheet({ mode: 'form', id: null });
  };
  const openEdit = (e) => {
    setErr('');
    setF({
      t: e.kind === 'CONSULT' ? 'c' : 'p',
      caseId: e.case_id ?? my.rows[0]?.id ?? '',
      hidden: !!e.case_hidden,
      ctype: e.consult_type && e.consult_type !== 'CLOSING' ? e.consult_type : e.consult_type ?? 'REGULAR',
      category: e.category,
      title: e.title ?? '',
      day: e.date,
      time: e.time ?? '',
      place: e.place ?? '',
    });
    setSheet({ mode: 'form', id: e.id });
  };

  const save = async () => {
    if (busy) return;
    const isC = f.t === 'c';
    if (isC && !f.caseId && !f.hidden) {
      setErr('아이를 골라 주세요.');
      return;
    }
    if (!isC && !(f.title || '').trim()) {
      setErr('제목을 적어 주세요.');
      return;
    }
    const payload = {
      kind: isC ? 'CONSULT' : 'OTHER',
      date: f.day,
      time: f.time || null,
      place: (f.place || '').trim() || null,
      ...(isC
        ? { consult_type: f.ctype, ...(f.hidden ? {} : { case_id: f.caseId }) }
        : { title: f.title.trim(), category: f.category ?? 'ETC' }),
    };
    setBusy(true);
    setErr('');
    try {
      if (sheet.id) await schedule.update(sheet.id, payload);
      else await schedule.create(payload);
      setDay(f.day);
      close();
      sched.reload();
    } catch (caught) {
      setErr(errorMessage(caught, '저장하지 못했어요. 잠시 후 다시 해 주세요.'));
    } finally {
      setBusy(false);
    }
  };

  const del = async () => {
    if (busy || !cur) return;
    setBusy(true);
    try {
      await schedule.remove(cur.id);
      close();
      sched.reload();
    } catch (caught) {
      setErr(errorMessage(caught, '삭제하지 못했어요.'));
    } finally {
      setBusy(false);
    }
  };

  const dayOpts = days.map((d) => ({ v: d.key, label: label(parseYmd(d.key)) }));
  if (f.day && !dayOpts.some((o) => o.v === f.day)) dayOpts.unshift({ v: f.day, label: label(parseYmd(f.day)) });
  const isC = (f.t || 'c') === 'c';
  const setFv = (k) => (ev) => setF({ ...f, [k]: ev.target.value });

  return (
    <>
      <div className="ma-calbar">
        <button type="button" className="ma-btn ma-btn-sm" aria-expanded={exp ? 'true' : 'false'} onClick={() => setExp(!exp)}>
          {exp ? '접기 ▴' : '펼치기 ▾'}
        </button>
        <b className="ma-calmon">{`${dayD.getFullYear()}년 ${dayD.getMonth() + 1}월`}</b>
        <button type="button" className="ma-btn ma-btn-sm" onClick={() => setDay(today)}>
          오늘
        </button>
      </div>
      {exp ? (
        <div className="ma-card ma-mcal" aria-label={`${dayD.getFullYear()}년 ${dayD.getMonth() + 1}월 달력`}>
          <div className="ma-mgrid">
            {DOW.map((w) => (
              <span key={w} className="ma-mdow">
                {w}
              </span>
            ))}
            {cells.map((c) => (
              <button
                key={c.key}
                type="button"
                className={'ma-mc' + (c.out ? ' ma-out' : '') + (c.sel ? ' ma-on' : '') + (c.today ? ' ma-today' : '')}
                aria-label={`${parseYmd(c.key).getMonth() + 1}월 ${c.n}일${c.dot ? ' · 일정 있음' : ''}`}
                aria-pressed={c.sel ? 'true' : 'false'}
                onClick={() => {
                  setDay(c.key);
                  setExp(false);
                }}
              >
                <span>{c.n}</span>
                <span className={c.dot ? 'ma-dot' : 'ma-dot ma-no'}></span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="ma-days" role="tablist" aria-label="이번 주">
          {days.map((d) => (
            <button
              key={d.key}
              type="button"
              role="tab"
              aria-selected={d.sel ? 'true' : 'false'}
              className={'ma-day' + (d.sel ? ' ma-on' : '') + (d.today ? ' ma-today' : '')}
              onClick={() => setDay(d.key)}
            >
              <small>{d.dow}</small>
              <b>{d.n}</b>
              <span className={d.dot ? 'ma-dot' : 'ma-dot ma-no'}></span>
            </button>
          ))}
        </div>
      )}
      <p className="ma-sec-t">{label(dayD)}</p>
      {sched.error && <span className="ma-err">{sched.error}</span>}
      {evs.map((e) => {
        const title = titleOf(e, names);
        const isCon = e.kind === 'CONSULT';
        return (
          <div
            key={e.id}
            className="ma-card ma-ev"
            role="button"
            tabIndex={0}
            aria-label={title + ' 자세히 보기'}
            onClick={() => {
              setAsk(false);
              setErr('');
              setSheet({ mode: 'view', id: e.id });
            }}
          >
            <div className="ma-ev-top">
              <span className="ma-ev-time">{e.time || '종일'}</span>
              <span className="ma-ev-body">
                <b>{title}</b>
                <span className="ma-note">{e.place || '장소 미정'}</span>
              </span>
              <span className={isCon ? 'ma-chip ma-gold' : 'ma-chip'}>{isCon ? '상담' : '개인 · 기관'}</span>
            </div>
            {isCon && (
              <div className="ma-ev-act">
                {e.case_id ? (
                  <Link className="ma-btn ma-btn-sm" to={`/AppBrief?case=${e.case_id}`} onClick={stop}>
                    상담 전 브리핑
                  </Link>
                ) : (
                  <span className="ma-btn ma-btn-sm" style={{ color: 'var(--mut)', cursor: 'default' }} onClick={stop}>
                    브리핑 준비 중
                  </span>
                )}
                {e.case_id ? (
                  <Link className="ma-btn ma-btn-sm ma-btn-p" to={`/AppRecord?case=${e.case_id}`} onClick={stop}>
                    녹음 시작
                  </Link>
                ) : (
                  <span className="ma-btn ma-btn-sm" style={{ color: 'var(--mut)', cursor: 'default' }} onClick={stop}>
                    녹음 시작
                  </span>
                )}
              </div>
            )}
          </div>
        );
      })}
      {!sched.loading && evs.length === 0 && <div className="ma-card ma-empty">일정이 없어요</div>}
      <button type="button" className="ma-btn ma-btn-p ma-fab" onClick={openAdd}>
        + 일정 추가
      </button>

      {sheet?.mode === 'view' && cur && (
        <div className="ma-ov" onClick={close}>
          <section className="ma-sheet" role="dialog" aria-modal="true" aria-label="일정 상세" onClick={stop}>
            <span className="ma-grab" aria-hidden="true"></span>
            <div className="ma-sh-hd">
              <b>{titleOf(cur, names)}</b>
              <span className={cur.kind === 'CONSULT' ? 'ma-chip ma-gold' : 'ma-chip'}>{cur.kind === 'CONSULT' ? '상담' : '개인 · 기관'}</span>
            </div>
            <div>
              {[
                ['날짜', label(parseYmd(cur.date))],
                ['시간', cur.time || '종일'],
                ['장소', cur.place || '—'],
                ...(cur.editable ? [] : [['만든 사람', cur.owner_name || '—']]),
              ].map(([k, v]) => (
                <div key={k} className="ma-row-k">
                  <span>{k}</span>
                  <span>{v}</span>
                </div>
              ))}
            </div>
            {err && <span className="ma-err">{err}</span>}
            {!cur.editable ? (
              <span className="ma-note">다른 상담원이 만든 일정이라 고칠 수 없어요.</span>
            ) : !ask ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <button type="button" className="ma-btn ma-btn-p" onClick={() => openEdit(cur)}>
                  수정
                </button>
                <button type="button" className="ma-btn ma-btn-red" onClick={() => setAsk(true)}>
                  삭제
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', padding: '14px', borderRadius: '12px', background: 'var(--redsoft)' }}>
                <b style={{ color: 'var(--red)' }}>이 일정을 삭제할까요?</b>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <button type="button" className="ma-btn" onClick={() => setAsk(false)}>
                    취소
                  </button>
                  <button type="button" className="ma-btn" style={{ background: 'var(--red)', borderColor: 'var(--red)', color: '#FFFFFF' }} onClick={del} disabled={busy}>
                    삭제
                  </button>
                </div>
              </div>
            )}
          </section>
        </div>
      )}

      {sheet?.mode === 'form' && (
        <div className="ma-ov" onClick={close}>
          <section className="ma-sheet" role="dialog" aria-modal="true" aria-label={sheet.id ? '일정 수정' : '일정 추가'} onClick={stop}>
            <span className="ma-grab" aria-hidden="true"></span>
            <div className="ma-sh-hd">
              <b>{sheet.id ? '일정 수정' : '일정 추가'}</b>
            </div>
            <div className="ma-seg" role="radiogroup" aria-label="일정 종류">
              <button type="button" role="radio" aria-checked={isC ? 'true' : 'false'} className={isC ? 'ma-on' : ''} onClick={() => setF({ ...f, t: 'c' })}>
                상담
              </button>
              <button type="button" role="radio" aria-checked={isC ? 'false' : 'true'} className={isC ? '' : 'ma-on'} onClick={() => setF({ ...f, t: 'p' })}>
                개인 · 기관
              </button>
            </div>
            {isC ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <label className="ma-fl">
                  <span className="ma-lb">아이</span>
                  <select className="ma-inp" value={f.caseId} onChange={setFv('caseId')} disabled={f.hidden}>
                    {f.hidden && <option value={f.caseId}>가려진 사례</option>}
                    {my.rows.map((r) => (
                      <option key={r.id} value={r.id}>
                        {childLabelOf(r)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="ma-fl">
                  <span className="ma-lb">상담 유형</span>
                  <select className="ma-inp" value={f.ctype} onChange={setFv('ctype')}>
                    {f.ctype === 'CLOSING' && <option value="CLOSING">{SCHEDULE_CONSULT_LABELS.CLOSING}</option>}
                    {KINDS.map(([k, l]) => (
                      <option key={k} value={k}>
                        {l}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            ) : (
              <label className="ma-fl">
                <span className="ma-lb">제목</span>
                <input className="ma-inp" type="text" placeholder="예) 팀 회의" value={f.title} onChange={setFv('title')} />
              </label>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <label className="ma-fl">
                <span className="ma-lb">날짜</span>
                <select className="ma-inp" value={f.day} onChange={setFv('day')}>
                  {dayOpts.map((o) => (
                    <option key={o.v} value={o.v}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="ma-fl">
                <span className="ma-lb">시간</span>
                <input className="ma-inp" type="time" value={f.time} onChange={setFv('time')} />
              </label>
            </div>
            <label className="ma-fl">
              <span className="ma-lb">장소</span>
              <input className="ma-inp" type="text" placeholder="예) 면담실 A" value={f.place} onChange={setFv('place')} />
            </label>
            {err && <span className="ma-err">{err}</span>}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '8px' }}>
              <button type="button" className="ma-btn" onClick={close}>
                취소
              </button>
              <button type="button" className="ma-btn ma-btn-p" onClick={save} disabled={busy}>
                저장
              </button>
            </div>
          </section>
        </div>
      )}
    </>
  );
}

function MonthLabel() {
  const now = new Date();
  return `${now.getFullYear()}년 ${now.getMonth() + 1}월`;
}

export default function AppSchedule() {
  return (
    <MobileAppShell cur="cal" screen="cal" sub={() => <MonthLabel />} title="일정">
      {(ctx) => <ScheduleBody {...ctx} />}
    </MobileAppShell>
  );
}
