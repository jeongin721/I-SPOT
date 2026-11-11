// 일정 · 월간 달력 + 일정 추가
// 원본: 11/02 프론트팀 디자인 '일정 · 월간 달력 + 일정 추가'(Schedule.dc.html)
//
// 서버 연결(2026-11-02): 일정은 useSchedule(GET/POST/PATCH/DELETE /schedule/events, API_CONTRACT 20절), 화면 값은
// src/data/screens/schedule.ts(scheduleValues). 상담 · 개인 · 기관 일정 추가 · 수정 · 삭제, 중요 표시, 팀 공유,
// 최초접수의 처리 기한(3 · 7 · 30일) 완료 표시가 서버에 저장된다. 종결보고서의 '종결평가 회의 일정 잡기' 는
// ?case=&preset=closure-meeting 으로 와서 추가 창이 열린 채 시작한다. '상담 전날 브리핑 자동 준비' 는 준비 중.
import { Fragment, useState } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import Notice from '../components/Notice';
import NotiBell from '../components/NotiBell';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useSchedule } from '../data/useSchedule';
import { needsLogin } from '../data/screens/common';
import { readScreenIds } from '../data/screens/links';
import {
  DATE_PARAM,
  PRESET_PARAM,
  dateFromParam,
  initialScheduleState,
  scheduleRange,
  scheduleValues,
} from '../data/screens/schedule';
import { useTheme } from '../theme';
import './Schedule.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = initialScheduleState(props.start, props.preset);
  }
  renderVals() {
    const setUi = (patch) => {
      this.setState(patch);
      if ('y' in patch || 'm' in patch) {
        const next = { ...this.state, ...patch };
        this.props.onMonth(next.y, next.m);
      }
    };
    return scheduleValues({ ...this.props, ui: this.state, setUi });
  }
}

// 보이는 달은 Logic 상태라 훅이 모른다. 처음 달로 부르고, 달이 바뀌면 Logic 이 onMonth 로 알린다.
/** ?date= 가 바뀌면(알림 종에서 그 날로 가기 — 일정 화면에 있을 때도) 새로 그린다. */
export default function Schedule(props) {
  const [params] = useSearchParams();
  return <ScheduleScreen key={params.get(DATE_PARAM) || ''} {...props} />;
}

function ScheduleScreen(props) {
  const session = useAuthSession();
  const [params] = useSearchParams();
  const [start] = useState(() => dateFromParam(params.get(DATE_PARAM)) ?? new Date());
  const [preset] = useState(() => ({ preset: params.get(PRESET_PARAM), caseId: readScreenIds(params).caseId }));
  const [month, setMonth] = useState(() => ({ y: start.getFullYear(), m: start.getMonth() }));
  const range = scheduleRange(month.y, month.m);
  const schedule = useSchedule(session, range);
  const theme = useTheme();
  const v = useDC(Logic, {
    ...props,
    session,
    schedule,
    preset,
    start,
    onMonth: (y, m) => setMonth((cur) => (cur.y === y && cur.m === m ? cur : { y, m })),
  });

  if (needsLogin(session)) return <Navigate to="/Login" replace />;

  const f = v.form || {};
  const ev = v.v || {};

  return (
    <div className="pg-Schedule">
      <div
        className={theme.cls}
        style={{
          minHeight: '1200px',
          background: '#E9E7E1',
          color: '#2B2A26',
          fontFamily: "'IBM Plex Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'stretch',
        }}
      >
        <Sidebar active="Schedule" session={session} />
        <main
          style={{
            flex: '999 1 640px',
            minWidth: '0',
            padding: '30px 36px 56px',
            display: 'flex',
            flexDirection: 'column',
            gap: '18px',
          }}
        >
          <div className="thm-bar">
            <NotiBell session={session} />
            <ThemeToggle />
          </div>
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 260px' }}>
              <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>일정</h1>
            </div>
          </header>
          <Notice value={v.notice} />

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '18px', alignItems: 'flex-start' }}>
            <section
              className="card"
              aria-label="월간 달력"
              style={{ flex: '3 1 620px', minWidth: '0', overflow: 'hidden' }}
            >
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  gap: '10px 14px',
                  padding: '16px 18px',
                }}
              >
                <button type="button" className="mnav" aria-label="이전 달" onClick={v.prevMonth}>
                  ‹
                </button>
                <b style={{ fontSize: '20px', minWidth: '120px', textAlign: 'center' }}>{v.monthLabel}</b>
                <button type="button" className="mnav" aria-label="다음 달" onClick={v.nextMonth}>
                  ›
                </button>
                <button type="button" className="btn btn-s" style={{ minHeight: '38px' }} onClick={v.goToday}>
                  오늘
                </button>
                <div role="group" aria-label="일정 종류 보기" className="seg" style={{ marginLeft: 'auto' }}>
                  <button type="button" className={v.fAllCls} onClick={v.showAll}>
                    전체
                  </button>
                  <button type="button" className={v.fCCls} onClick={v.showC}>
                    ● 상담
                  </button>
                  <button type="button" className={v.fPCls} onClick={v.showP}>
                    ■ 개인 · 기관
                  </button>
                  <button type="button" className={v.fICls} onClick={v.showI} style={{ color: '#A33B2E' }}>
                    ! 중요
                  </button>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(0, 1fr))', background: '#F7F6F2' }}>
                <span className="dow">일</span>
                <span className="dow">월</span>
                <span className="dow">화</span>
                <span className="dow">수</span>
                <span className="dow">목</span>
                <span className="dow">금</span>
                <span className="dow">토</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(0, 1fr))' }}>
                {(v.cells || []).map((c, cIndex) => (
                  <Fragment key={cIndex}>
                    <button
                      type="button"
                      className="cell"
                      onClick={c.pick}
                      aria-label={c.aria}
                      style={{ background: c.bg, boxShadow: c.ring }}
                    >
                      <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span
                          style={{
                            width: '26px',
                            height: '26px',
                            borderRadius: '50%',
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '13px',
                            fontWeight: c.fw,
                            background: c.numBg,
                            color: c.numFg,
                          }}
                        >
                          {c.num}
                        </span>
                        <span style={{ fontSize: '10px', color: '#7A776F' }}>{c.holiday}</span>
                      </span>
                      {(c.pills || []).map((p, pIndex) => (
                        <Fragment key={pIndex}>
                          <span
                            className="pill"
                            onClick={p.open}
                            title={p.tip}
                            style={{ background: p.bg, color: p.fg, fontWeight: p.fw }}
                          >
                            <span
                              style={{
                                width: '7px',
                                height: '7px',
                                flex: 'none',
                                marginTop: '4px',
                                borderRadius: p.radius,
                                background: p.dot,
                              }}
                            ></span>
                            <span className="pl-tx">
                              {p.hasHead ? (
                                <span className="pl-head">
                                  <span className="pl-time">{p.time}</span>
                                  <b>{p.who}</b>
                                </span>
                              ) : null}
                              <span className="pl-ttl">{p.body}</span>
                            </span>
                          </span>
                        </Fragment>
                      ))}
                      <span style={{ fontSize: '11px', color: '#6E6A62', paddingLeft: '4px' }}>{c.more}</span>
                    </button>
                  </Fragment>
                ))}
              </div>
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '8px 20px',
                  padding: '14px 18px',
                  fontSize: '12px',
                  color: '#66625A',
                  borderTop: '1px solid #EAE7DF',
                }}
              >
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#7A776F' }}></span>
                  상담 일정 {v.countC}건
                </span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '10px', height: '10px', borderRadius: '2px', background: '#B9B2A2' }}></span>
                  개인 · 기관 일정 {v.countP}건
                </span>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    color: '#A33B2E',
                    fontWeight: '500',
                  }}
                >
                  <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#A33B2E' }}></span>
                  중요 {v.countI}건
                </span>
              </div>
            </section>

            <aside
              className="card"
              aria-label="선택한 날 일정"
              style={{
                flex: '1 1 320px',
                minWidth: '0',
                padding: '20px 22px',
                display: 'flex',
                flexDirection: 'column',
                gap: '14px',
              }}
            >
              {v.notAdding ? (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ flex: '1' }}>
                      <div className="note">선택한 날</div>
                      <b style={{ fontSize: '19px' }}>{v.selLabel}</b>
                    </div>
                    <button type="button" className="btn btn-p" onClick={v.openAdd}>
                      + 일정 추가
                    </button>
                  </div>
                  <div>
                    {(v.dayEvents || []).map((e, eIndex) => (
                      <Fragment key={eIndex}>
                        <div
                          className="ev ev-clk"
                          role="button"
                          tabIndex={0}
                          aria-label={e.aria}
                          onClick={e.open}
                          onKeyDown={e.key}
                        >
                          <span style={{ fontSize: '13px', color: '#66625A' }}>{e.time}</span>
                          <span
                            style={{
                              marginTop: '5px',
                              width: '12px',
                              height: '12px',
                              borderRadius: e.radius,
                              background: e.dot,
                            }}
                          ></span>
                          <span style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            <b style={{ fontWeight: e.fw, color: e.titleFg }}>{e.title}</b>
                            <span style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '6px' }}>
                              <span className="chip" style={{ background: e.tagBg, color: e.tagFg }}>
                                {e.tag}
                              </span>
                              <span className="note">{e.sub}</span>
                            </span>
                          </span>
                          <button
                            type="button"
                            className="impb"
                            aria-pressed={e.impOn}
                            onClick={e.toggleImp}
                            disabled={e.impDisabled}
                            style={{ background: e.impBg, color: e.impFg, borderColor: e.impBd }}
                          >
                            {e.impLabel}
                          </button>
                        </div>
                      </Fragment>
                    ))}
                    {v.noEvents ? (
                      <p className="note" style={{ margin: '8px 0' }}>
                        일정 없음
                      </p>
                    ) : null}
                  </div>
                </>
              ) : null}

              {v.viewing ? (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <button type="button" className="btn btn-sm btn-s" onClick={v.vBack} aria-label="일정 목록으로 돌아가기">
                      ← 목록
                    </button>
                    <span className="note" style={{ marginLeft: 'auto' }}>
                      {ev.kind}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                    <span
                      style={{
                        marginTop: '8px',
                        width: '12px',
                        height: '12px',
                        flex: 'none',
                        borderRadius: ev.radius,
                        background: ev.dot,
                      }}
                    ></span>
                    <b style={{ fontSize: '20px', lineHeight: '1.4', color: ev.titleFg }}>{ev.title}</b>
                  </div>
                  <div className="vd-box">
                    {(ev.rows || []).map((r, rIndex) => (
                      <div key={rIndex} className="vd-row">
                        <span className="vd-k">{r.k}</span>
                        <span className="vd-v">{r.v}</span>
                      </div>
                    ))}
                  </div>
                  {ev.isDl ? (
                    <>
                      <p className="note" style={{ margin: '0' }}>
                        처리 기한 일정은 최초접수 일정에 맞춰 자동으로 만들어져요. 날짜를 바꾸거나 지우려면 최초접수 일정에서 수정 ·
                        삭제해 주세요.
                      </p>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'flex-end' }}>
                        <button type="button" className="btn btn-s" onClick={ev.goBase}>
                          최초접수 일정 보기
                        </button>
                        <button type="button" className={`btn ${ev.doneCls}`} onClick={ev.toggleDone}>
                          {ev.doneLabel}
                        </button>
                      </div>
                    </>
                  ) : null}
                  {ev.canEdit ? (
                    <>
                      {ev.noAsk ? (
                        <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                          <button type="button" className="btn btn-p" onClick={ev.edit}>
                            수정
                          </button>
                          <button type="button" className="btn btn-s vd-del" onClick={ev.askDel}>
                            삭제
                          </button>
                        </div>
                      ) : null}
                      {ev.ask ? (
                        <div className="vd-ask" role="alertdialog" aria-label="일정 삭제 확인">
                          <b>이 일정을 삭제할까요?</b>
                          <span className="note">{ev.askNote}</span>
                          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                            <button type="button" className="btn btn-s" onClick={ev.cancelDel}>
                              취소
                            </button>
                            <button type="button" className="btn vd-del-go" onClick={ev.del}>
                              삭제
                            </button>
                          </div>
                        </div>
                      ) : null}
                    </>
                  ) : null}
                </>
              ) : null}

              {v.adding ? (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <b style={{ fontSize: '19px', flex: '1' }}>{v.formTitle}</b>
                    <span className="note">{v.formDateLabel}</span>
                  </div>
                  <div role="radiogroup" aria-label="일정 종류" style={{ display: 'flex', gap: '8px' }}>
                    <button
                      type="button"
                      role="radio"
                      aria-checked={v.isC ? 'true' : 'false'}
                      className="kind"
                      onClick={v.kindC}
                      style={{ borderColor: v.kcBorder, background: v.kcBg }}
                    >
                      <b style={{ fontWeight: '700' }}>● 상담 일정</b>
                    </button>
                    <button
                      type="button"
                      role="radio"
                      aria-checked={v.isP ? 'true' : 'false'}
                      className="kind"
                      onClick={v.kindP}
                      style={{ borderColor: v.kpBorder, background: v.kpBg }}
                    >
                      <b style={{ fontWeight: '700' }}>■ 개인 · 기관 일정</b>
                    </button>
                  </div>

                  {v.isC ? (
                    <>
                      <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <span className="lb">아이 (사례)</span>
                        <select className="in" value={f.child} onChange={v.setChild} disabled={v.caseLocked}>
                          {(v.caseOptions || []).map((o) => (
                            <option key={o.value} value={o.value}>
                              {o.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <span className="lb">상담 유형</span>
                        <select className="in" value={f.ctype} onChange={v.setCtype}>
                          {(v.consultOptions || []).map((o) => (
                            <option key={o.value} value={o.value}>
                              {o.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    </>
                  ) : null}
                  {v.isP ? (
                    <>
                      <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <span className="lb">분류</span>
                        <select className="in" value={f.pcat} onChange={v.setPcat}>
                          {(v.categoryOptions || []).map((o) => (
                            <option key={o.value} value={o.value}>
                              {o.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      {v.isIntake ? (
                        <>
                          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            <span className="lb">아이 (사례)</span>
                            <select className="in" value={f.child} onChange={v.setChild} disabled={v.caseLocked}>
                              {(v.caseOptions || []).map((o) => (
                                <option key={o.value} value={o.value}>
                                  {o.label}
                                </option>
                              ))}
                            </select>
                          </label>
                          <div className="dl-box">
                            <b style={{ fontSize: '13px' }}>학대 판정 후 처리 기한 · 자동 추가</b>
                            {(v.dlPreview || []).map((p, pIndex) => (
                              <div key={pIndex} className="dl-row">
                                <span className="dl-n">{p.n}</span>
                                <span style={{ flex: '1' }}>{p.task}</span>
                                <span className="note">{p.due}까지</span>
                              </div>
                            ))}
                            <span className="note">저장하면 기한 일정이 달력에 표시되고 알림에 추가돼요.</span>
                          </div>
                        </>
                      ) : null}
                      {v.notIntake ? (
                        <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          <span className="lb">제목</span>
                          <input
                            className="in"
                            type="text"
                            placeholder="예) 팀 회의"
                            value={f.title}
                            onChange={v.setTitle}
                          />
                        </label>
                      ) : null}
                    </>
                  ) : null}

                  {v.isEdit ? (
                    <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <span className="lb">날짜</span>
                      <input className="in" type="date" value={f.date} onChange={v.setDate} />
                    </label>
                  ) : null}
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <label style={{ flex: '1', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <span className="lb">시간</span>
                      <input className="in" type="time" value={f.time} onChange={v.setTime} />
                    </label>
                    <label style={{ flex: '1.4', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <span className="lb">장소</span>
                      <input className="in" type="text" placeholder="예) 면담실 A" value={f.place} onChange={v.setPlace} />
                    </label>
                  </div>

                  {v.isC ? (
                    <div
                      style={{
                        padding: '12px 14px',
                        borderRadius: '12px',
                        background: '#F7F6F2',
                        fontSize: '13px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '6px',
                      }}
                    >
                      <label style={{ display: 'flex', gap: '8px', alignItems: 'center' }} title={v.briefNote}>
                        <input
                          type="checkbox"
                          defaultChecked
                          disabled
                          style={{ width: '16px', height: '16px', accentColor: '#2B2A26' }}
                        />
                        상담 전날 <a href="#/CaseDetail">브리핑</a> 자동 준비
                      </label>
                      <span className="note">아이 앱 알림 없음 (보호자 노출 방지)</span>
                    </div>
                  ) : null}
                  {v.isP ? (
                    <div style={{ padding: '12px 14px', borderRadius: '12px', background: '#F7F6F2', fontSize: '13px' }}>
                      <label style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <input
                          type="checkbox"
                          checked={Boolean(v.sharedOn)}
                          disabled={v.sharedDisabled}
                          onChange={v.toggleShared}
                          style={{ width: '16px', height: '16px', accentColor: '#2B2A26' }}
                        />
                        팀 일정으로 공유
                      </label>
                    </div>
                  ) : null}

                  <button
                    type="button"
                    role="switch"
                    aria-checked={v.formImpOn}
                    onClick={v.toggleFormImp}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      minHeight: '46px',
                      padding: '0 14px',
                      borderRadius: '12px',
                      border: `1.5px solid ${v.formImpBd}`,
                      background: v.formImpBg,
                      color: v.formImpFg,
                      font: 'inherit',
                      fontSize: '14px',
                      fontWeight: '700',
                      cursor: 'pointer',
                      textAlign: 'left',
                    }}
                  >
                    <span
                      style={{
                        width: '18px',
                        height: '18px',
                        borderRadius: '5px',
                        border: `1.5px solid ${v.formImpBd}`,
                        background: v.formImpBox,
                        color: '#FFFFFF',
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '12px',
                      }}
                    >
                      {v.formImpMark}
                    </span>
                    중요 일정 (빨간색 표시)
                  </button>

                  {v.saveNote ? (
                    <p className="note" role="status" style={{ margin: '0' }}>
                      {v.saveNote}
                    </p>
                  ) : null}
                  <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                    <button type="button" className="btn btn-s" onClick={v.cancelAdd}>
                      취소
                    </button>
                    <button type="button" className="btn btn-p" onClick={v.save} disabled={!v.canSave}>
                      {v.saveLabel}
                    </button>
                  </div>
                </>
              ) : null}
            </aside>
          </div>
        </main>
      </div>
    </div>
  );
}
