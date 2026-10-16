// 아이 연계 · 긴급 알림 + 아이 목록 (응답 · 상태)
// 원본: 다솔 님 디자인 counselor-web-design/ChildLink.dc.html (front_new 브랜치). 화면 값은 아직 예시(가상) 데이터다.
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useTheme } from '../theme';
import './ChildLink.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { f: 'need' };
  }
  renderVals() {
    const KIDS = {
      minjun: {
        name: '장민준',
        short: '민준',
        age: '9세',
        id: 'C-2026-0277',
        risk: '상',
        types: '신체',
        reason: '긴급',
        rCls: 'chip c-urgent',
        last: '오늘 08:12',
        urgent: true,
        connected: true,
        days: '111011111101111111111',
        next: '10/29 정기상담',
        now: [
          ['공통 2', '어제 누가 아프게 한 적 있어?', '없어', '물건으로 맞았어 · 여러 번'],
          ['공통 3', '오늘 기분은?', '보통', '무서워'],
          ['공통 1', '어젯밤 잘 잤어?', '괜찮았어', '잘 못 잤어'],
        ],
        quote: '',
        ai: '도구 사용 · 반복 응답이라 긴급 기준에 해당해요. 지난 3주 동안 같은 문항 답은 모두 "없어"였어요. 아이 안전 확인과 기관 내부 보고 여부는 상담사가 판단해 주세요. AI는 신고하거나 연락하지 않아요.',
        state: '근거 확인 필요',
        stCls: 'chip c-check',
        src: '오늘 08:12 체크인 · 공통 1 · 2 · 3',
        related: '7회차(9/14) 상담 · 아동 발화 "아빠가 화나면 물건을 던져요" (상담사 확인 완료)',
        hist: [
          ['아프게 한 적', ['없어', '없어', '없어', '여러 번']],
          ['오늘 기분', ['좋아', '보통', '보통', '무서워']],
          ['잠', ['괜찮았어', '괜찮았어', '괜찮았어', '잘 못 잤어']],
        ],
        q: ['QB-P-04', '다친 곳을 누가 봐 줬는지 알려 줄래?'],
      },
      jiho: {
        name: '박지호',
        short: '지호',
        age: '11세',
        id: 'C-2026-0389',
        risk: '중',
        types: '방임 · 정서',
        reason: '확인 필요',
        rCls: 'chip c-check',
        last: '어제 21:05',
        connected: true,
        days: '111111011111111111111',
        next: '10/22 정기상담 5회차',
        now: [
          ['QB-N-12', '이번 주 저녁을 혼자 먹은 날은?', '1~2일', '5일 이상'],
          ['유형 N-5', '어젯밤 집에 어른이 있었어?', '늦게 왔어', '혼자 잤어'],
          ['공통 3', '오늘 기분은?', '보통', '조금 슬퍼'],
        ],
        quote: '엄마가 요즘 밤에 집에 안 들어와',
        ai: '저녁 · 밤 시간에 혼자 있는 날이 3주째 늘고 있어요. 3회차 상담 진술과 같은 방향이에요. 다음 상담에서 저녁 시간 돌봄을 확인해 보세요.',
        state: '확인 중',
        stCls: 'chip c-ing',
        src: '어제 21:05 QB-N-12 · 유형 N-5 응답 · 21:06 자유 글',
        related: '3회차(9/30) 상담일지 · 아동 진술 "요즘 저녁은 혼자 라면 먹어요"',
        hist: [
          ['저녁 혼자', ['0일', '1~2일', '1~2일', '5일 이상']],
          ['밤에 어른', ['있었어', '있었어', '늦게 왔어', '혼자 잤어']],
          ['오늘 기분', ['좋아', '보통', '보통', '조금 슬퍼']],
        ],
        q: ['QB-N-14', '이번 주에 밤에 집에 어른이 없었던 날은 며칠이야?'],
      },
      dohyun: {
        name: '김도현',
        short: '도현',
        age: '8세',
        id: 'C-2026-0412',
        risk: '상',
        types: '신체 · 정서',
        reason: '연락 요청',
        rCls: 'chip c-check',
        last: '어제 19:40',
        connected: true,
        days: '110111111111011111111',
        next: '10/12 정기상담 7회차',
        now: [
          ['연락 버튼', '선생님께 연락하고 싶어?', '—', '빨리 연락해 주세요'],
          ['공통 3', '오늘 기분은?', '보통', '조금 슬퍼'],
        ],
        quote: '선생님이랑 얘기하고 싶어요',
        ai: '아이가 직접 연락을 요청했어요. 오늘 안에 통화 일정을 잡는 것을 권해요. 6회차 STT 검수가 아직 남아 있어요.',
        state: '확인 중',
        stCls: 'chip c-ing',
        src: '어제 19:40 연락 요청 버튼 · 공통 3',
        related: '6회차(10/6) 녹취 00:38 · 아동 발화 "아빠가 화나면 무서워요"',
        hist: [
          ['오늘 기분', ['좋아', '보통', '보통', '조금 슬퍼']],
          ['잠', ['괜찮았어', '괜찮았어', '괜찮았어', '괜찮았어']],
          ['연락 요청', ['—', '—', '—', '요청']],
        ],
        q: ['QB-E-05', '무서운 마음이 들 때 어디에 가 있으면 마음이 편해?'],
      },
      yerin: {
        name: '정예린',
        short: '예린',
        age: '9세',
        id: 'C-2026-0338',
        risk: '중',
        types: '방임',
        reason: '확인 필요',
        rCls: 'chip c-check',
        last: '어제 20:30',
        connected: true,
        days: '111111111111111111111',
        next: '미정',
        now: [
          ['공통 3', '오늘 기분은?', '슬퍼', '슬퍼'],
          ['QB-N-01', '어제 밥을 몇 번 먹었어?', '2번', '1번'],
        ],
        quote: '',
        ai: '한 번이 아니라 2주 동안 "슬퍼"가 이어지고 있어요(14일 중 9일). 식사 횟수도 줄었어요. 다음 상담 전에 안부 연락을 해 보세요.',
        state: '근거 확인 필요',
        stCls: 'chip c-check',
        src: '9/28~어제 체크인 공통 3 · QB-N-01 (14회)',
        related: '4회차(10/7) 상담일지 · "요즘 학교 가기 싫어요"',
        hist: [
          ['오늘 기분', ['좋아', '보통', '슬퍼', '슬퍼']],
          ['밥 횟수', ['3번', '2번', '2번', '1번']],
          ['잠', ['괜찮았어', '괜찮았어', '잘 못 잤어', '괜찮았어']],
        ],
        q: ['QB-N-01', '요즘 밥은 주로 누가 챙겨 줘?'],
      },
      seoyun: {
        name: '이서윤',
        short: '서윤',
        age: '13세',
        id: 'C-2026-0351',
        risk: '상',
        types: '신체 · 정서',
        reason: '아이가 보낸 말',
        rCls: 'chip c-sky',
        last: '어제 22:10',
        connected: true,
        days: '111101111111110111111',
        next: '오늘 16:00 9회차',
        now: [
          ['QB-E-05', '누가 "말하면 혼난다"처럼 겁을 준 적 있어?', '없어', '1번'],
          ['공통 3', '오늘 기분은?', '보통', '조금 걱정돼'],
        ],
        quote: '다음 상담 때 말할 게 있어요',
        ai: '8회차 상담에서 나온 함구 요구 진술과 같은 내용의 응답이 처음 나왔어요. 아이가 먼저 이야기를 꺼낼 수 있도록 다음 상담 시작을 열어 두세요.',
        state: '확인 중',
        stCls: 'chip c-ing',
        src: '10/6 QB-E-05 응답 · 어제 22:10 자유 글',
        related: '8회차(10/2) 녹취 01:08 · 아동 발화 "말하면 더 혼난다고 했어요"',
        hist: [
          ['겁 준 적', ['없어', '없어', '없어', '1번']],
          ['오늘 기분', ['보통', '보통', '조금 걱정돼', '조금 걱정돼']],
          ['잠', ['괜찮았어', '괜찮았어', '괜찮았어', '괜찮았어']],
        ],
        q: ['QB-N-01', '어제 밥을 몇 번 먹었어?'],
      },
      haeun: {
        name: '윤하은',
        short: '하은',
        age: '10세',
        id: 'C-2026-0298',
        risk: '중',
        types: '정서',
        reason: '안부 연락 우선',
        rCls: 'chip c-sand',
        last: '9/28',
        connected: true,
        days: '111100000000000000000',
        next: '10/13 전화상담',
        now: [],
        quote: '',
        ai: '14일째 응답이 없어요. 위험 신호가 아니라 연락할 이유예요. 위험도에는 반영하지 않아요. 앱 알림이 꺼졌는지, 기기를 쓸 수 있는지 안부 통화로 확인해 보세요.',
        state: '확인 중',
        stCls: 'chip c-ing',
        src: '마지막 응답 9/28 · 이후 무응답',
        related: '5회차(9/26) 상담일지 · "휴대폰은 언니랑 같이 써요"',
        hist: [
          ['오늘 기분', ['보통', '좋아', '', '']],
          ['잠', ['괜찮았어', '괜찮았어', '', '']],
          ['학교', ['괜찮아', '괜찮아', '', '']],
        ],
        q: ['', ''],
      },
      yuna: {
        name: '신유나',
        short: '유나',
        age: '8세',
        id: 'C-2026-0229',
        risk: '하',
        types: '정서',
        reason: '일반',
        rCls: 'chip c-normal',
        last: '어제 20:02',
        connected: true,
        days: '110110101101011011011',
        next: '10/20 방문상담',
        now: [['공통 3', '오늘 기분은?', '좋아', '좋아']],
        quote: '',
        ai: '최근 응답에 변화가 없어요. 따로 확인할 점이 없어요.',
        state: '확인 완료',
        stCls: 'chip c-ok',
        src: '최근 3주 체크인 14회',
        related: '—',
        hist: [
          ['오늘 기분', ['좋아', '좋아', '보통', '좋아']],
          ['잠', ['괜찮았어', '괜찮았어', '괜찮았어', '괜찮았어']],
        ],
        q: ['', ''],
      },
      siwoo: {
        name: '강시우',
        short: '시우',
        age: '7세',
        id: 'C-2026-0312',
        risk: '하',
        types: '정서',
        reason: '안정 · 종결 검토 중',
        rCls: 'chip c-ok',
        last: '어제 19:15',
        connected: true,
        days: '111111111111111111111',
        next: '10/14 종결 상담',
        now: [['공통 3', '오늘 기분은?', '좋아', '좋아']],
        quote: '',
        ai: '4주 연속 기분 응답이 "좋아 · 보통"이에요. 종결 검토서 근거로 들어가 있어요.',
        state: '확인 완료',
        stCls: 'chip c-ok',
        src: '체크인 공통 3 · 28회',
        related: '12회차(10/1) · 아동이 안전 계획을 자기 말로 설명함',
        hist: [
          ['오늘 기분', ['좋아', '좋아', '보통', '좋아']],
          ['잠', ['괜찮았어', '괜찮았어', '괜찮았어', '괜찮았어']],
        ],
        q: ['', ''],
      },
      harin: {
        name: '조하린',
        short: '하린',
        age: '14세',
        id: 'C-2026-0251',
        risk: '하',
        types: '방임',
        reason: '앱 미연결 · 초대 전',
        rCls: 'chip c-normal',
        last: '—',
        connected: false,
        days: '',
        next: '10/15 정기상담',
        now: [],
        quote: '',
        ai: '아직 앱을 연결하지 않았어요. 다음 상담에서 초대 코드를 안내할 수 있어요.',
        state: '—',
        stCls: 'chip c-normal',
        src: '—',
        related: '—',
        hist: [],
        q: ['', ''],
      },
    };
    const ORDER = ['minjun', 'jiho', 'dohyun', 'yerin', 'seoyun', 'haeun', 'yuna', 'siwoo', 'harin'];
    const COLS = ['3주 전', '2주 전', '지난주', '이번'];

    const s = this.state;
    const needKeys = ['minjun', 'jiho', 'dohyun', 'yerin', 'seoyun', 'haeun'];
    const keys = s.f === 'need' ? ORDER.filter((x) => needKeys.includes(x)) : ORDER;
    const rows = keys.map((key) => {
      const k = KIDS[key];
      const ds = (k.days || '').split('');
      return {
        name: s.real ? k.name : '○' + k.short,
        age: k.age,
        id: k.id,
        ini: s.real ? k.name.slice(0, 1) : k.short.slice(0, 1),
        last: k.last,
        reason: k.reason,
        rCls: k.reason === '긴급' ? 'chip c-urgent' : 'chip c-normal',
        count: k.connected ? `${ds.filter((c) => c === '1').length} / 21일` : '미연결',
      };
    });
    const filters = [
      ['need', '확인할 아이 6'],
      ['all', '전체 9'],
    ].map(([v, l]) => ({ label: l, cls: s.f === v ? 'on' : '', pick: () => this.setState({ f: v }) }));
    return {
      rows,
      filters,
      alertName: s.real ? KIDS.minjun.name : '○' + KIDS.minjun.short,
      real: !!s.real,
      tgBg: s.real ? '#2B2A26' : '#DAD5C9',
      tgX: s.real ? '16px' : '2px',
      toggleReal: () => this.setState({ real: !s.real }),
    };
  }
}

export default function ChildLink(props) {
  // 사이드바의 내 정보 · 로그아웃 · '관리자 메뉴'(관리자일 때만)에만 쓴다. 이 화면의 값은 아직 예시 데이터다.
  const session = useAuthSession();
  const theme = useTheme();
  const v = useDC(Logic, props);
  return (
    <div className="pg-ChildLink">
      <div
        className={theme.cls}
        style={{
          minHeight: '1000px',
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
        <Sidebar active="ChildLink" session={session} />
        <main
          style={{
            flex: '999 1 640px',
            minWidth: '0',
            padding: '30px 36px 56px',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
          }}
        >
          <div className="thm-bar">
            <ThemeToggle />
          </div>
          <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>아이 연계</h1>

          <A
            role="alert"
            to="/ChildDetail"
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: '10px 14px',
              padding: '16px 20px',
              borderRadius: '16px',
              background: '#F7E4DF',
              textDecoration: 'none',
              color: '#A33B2E',
            }}
          >
            <span className="chip c-urgent" style={{ background: '#FFFFFF' }}>
              긴급
            </span>
            <span style={{ flex: '1 1 320px' }}>
              <b>{v.alertName}</b> · 오늘 08:12 "물건으로 맞았어 · 여러 번" · 아이 화면 112 · 1388 안내됨
            </span>
            <b style={{ fontSize: '14px' }}>바로 확인 →</b>
          </A>

          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 12px' }}>
            <input
              className="inp"
              type="search"
              aria-label="이름 또는 사례 ID 검색"
              placeholder="이름 · 사례 ID 검색"
              style={{ flex: '1 1 240px' }}
            />
            <div role="group" aria-label="상태" className="seg">
              {(v.filters || []).map((f, fIndex) => (
                <Fragment key={fIndex}>
                  <button type="button" className={f.cls} onClick={f.pick}>
                    {f.label}
                  </button>
                </Fragment>
              ))}
            </div>
            <button type="button" className="tg" aria-pressed={v.real} onClick={v.toggleReal}>
              <span
                style={{
                  width: '34px',
                  height: '20px',
                  borderRadius: '10px',
                  background: v.tgBg,
                  position: 'relative',
                  display: 'inline-block',
                }}
              >
                <span
                  style={{
                    position: 'absolute',
                    top: '2px',
                    left: v.tgX,
                    width: '16px',
                    height: '16px',
                    borderRadius: '50%',
                    background: '#FFFFFF',
                    boxShadow: '0 1px 2px rgba(0,0,0,.2)',
                  }}
                ></span>
              </span>
              실명 보기
            </button>
          </section>
          {v.real ? (
            <>
              <p className="note" style={{ margin: '-8px 0 0' }}>
                실명 표시 중 · 열람 기록 남음
              </p>
            </>
          ) : null}

          <section className="card" style={{ overflowX: 'auto' }}>
            <table className="tbl" style={{ minWidth: '640px' }}>
              <thead>
                <tr>
                  <th scope="col">아동 이름</th>
                  <th scope="col">최근 3주 응답</th>
                  <th scope="col">마지막 응답</th>
                  <th scope="col">상태</th>
                </tr>
              </thead>
              <tbody>
                {(v.rows || []).map((r, rIndex) => (
                  <Fragment key={rIndex}>
                    <tr>
                      <td>
                        <A className="nm" to="/ChildDetail">
                          <span className="av" style={{ width: '34px', height: '34px', fontSize: '13px' }}>
                            {r.ini}
                          </span>
                          <span>
                            {r.name} <span className="note">{r.age}</span>
                            <span className="note" style={{ display: 'block', fontWeight: '400' }}>
                              {r.id}
                            </span>
                          </span>
                        </A>
                      </td>
                      <td>
                        <b>{r.count}</b>
                      </td>
                      <td>{r.last}</td>
                      <td>
                        <span className={r.rCls}>{r.reason}</span>
                      </td>
                    </tr>
                  </Fragment>
                ))}
              </tbody>
            </table>
          </section>
        </main>
      </div>
    </div>
  );
}
