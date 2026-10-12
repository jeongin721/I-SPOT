// 탭 2 › 회차 상세 (1~4단계 처리로 바로 가기)
// 원본: I-SPOT 디자인 캔버스 보드 SessionDetail.dc.html (자동 변환 후 다듬어 쓰세요)
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import './SessionDetail.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { n: 8 };
  }
  renderVals() {
    const RAW = {
      8: {
        date: '2026-10-02',
        kind: '방문상담 · 24분',
        status: '처리 중',
        st: 'chip c-check',
        sig: '채택 3 · 보류 1',
        proc: true,
        sttState: '검수 중 · 저신뢰 3곳',
        sttCls: 'chip c-check',
        lines: [
          { t: '00:41', sp: '아동', s: '아빠가 또 화났어요. 저한테 소리 지르고… 많이 때렸어요.', c: '62%' },
          { t: '01:08', sp: '아동', s: '등이랑 팔이요. 근데 말하면 더 혼난다고 했어요.', c: '58%' },
          { t: '01:36', sp: '아동', s: '무서웠어요.', c: '91%' },
          { t: '02:15', sp: '화자?', s: '밥도 안 줄 때가 있어요.', c: '70%' },
        ],
        diaryState: '작성 전',
        diaryCls: 'chip c-check',
        diary: '아직 작성하지 않았어요. 회차 처리 3단계에서 AI 초안을 받아 작성해요.',
        diaryBtn: '요약 · 일지 작성하러 가기',
        sumState: '작성 전',
        sumCls: 'chip c-check',
        summary: '요약은 회차 처리 3단계에서 확정돼요.',
        ai: '아동이 가정 내 상황에 대한 불안감을 표현하였으며 신체적 증상(등 · 팔 통증)을 호소함. 보호자에게서 "말하면 더 혼난다"는 말을 들었다고 진술함. 식사 관련 발화는 화자 확인 필요.',
        sigs: [
          ['신체', '직접 신체 가해 · 00:41'],
          ['신체', '상해 부위 진술 · 01:08'],
          ['정서', '위협 · 공포 유발 · 01:08, 01:36'],
          ['방임', '기본 보호 · 양육 (보류) · 02:15'],
        ],
      },
      7: {
        date: '2026-09-18',
        kind: '정기상담 · 50분',
        status: '확정',
        st: 'chip c-ok',
        sig: '채택 2',
        proc: false,
        sttState: '검수 완료',
        sttCls: 'chip c-ok',
        lines: [
          { t: '02:40', sp: '아동', s: '무서우면 할머니한테 전화할 거예요.', c: '93%' },
          { t: '05:10', sp: '아동', s: '아빠가 그 얘기 하지 말랬어요.', c: '88%' },
        ],
        diaryState: '확정',
        diaryCls: 'chip c-ok',
        diary:
          '안전 계획을 아동과 함께 정리함. 위급 시 조모에게 연락하기로 함. 보호자가 상담 내용을 말하지 말라고 했다는 진술이 있어 진술 압박 여부를 계속 확인하기로 함.',
        diaryBtn: '일지 수정',
        sumState: '확정',
        sumCls: 'chip c-ok',
        summary: '안전 계획 수립 · 진술 압박 진술 1건 · 조모 연락 체계 확인.',
        ai: '아동과 안전 계획을 수립함. 보호자의 함구 요구 정황이 확인됨.',
        sigs: [
          ['정서', '위협 · 공포 유발 · 05:10'],
          ['정서', '진술 압박 · 05:10'],
        ],
      },
      6: {
        date: '2026-09-04',
        kind: '정기상담 · 45분',
        status: '확정',
        st: 'chip c-ok',
        sig: '채택 2',
        proc: false,
        sttState: '검수 완료',
        sttCls: 'chip c-ok',
        lines: [
          { t: '03:20', sp: '아동', s: '아빠가 소리 지르는 게 제일 싫어요.', c: '95%' },
          { t: '05:02', sp: '아동', s: '맞은 적은… 잘 모르겠어요.', c: '90%' },
        ],
        diaryState: '확정',
        diaryCls: 'chip c-ok',
        diary:
          '아버지의 고성에 대한 두려움을 표현함. 신체 체벌 질문에는 "잘 모르겠다"고 답함. 진술 변화를 기록해 둠.',
        diaryBtn: '일지 수정',
        sumState: '확정',
        sumCls: 'chip c-ok',
        summary: '고성에 대한 두려움 · 체벌 질문에 모호한 답.',
        ai: '아동이 보호자의 고성에 두려움을 표현함.',
        sigs: [
          ['신체', '직접 신체 가해 · 05:02'],
          ['정서', '위협 · 공포 유발 · 03:20'],
        ],
      },
    };
    const DATES = ['', '2026-07-31', '2026-08-07', '2026-08-14', '2026-08-21', '2026-08-28'];
    const getS = (n) =>
      RAW[n] || {
        date: DATES[n],
        kind: n === 1 ? '초기면담 · 40분' : '정기상담 · 45분',
        status: '확정',
        st: 'chip c-ok',
        proc: false,
        sig: n <= 3 ? '신호 없음' : '채택 ' + (n === 5 ? 3 : 1),
        sttState: '검수 완료',
        sttCls: 'chip c-ok',
        lines: [
          {
            t: '01:00',
            sp: '아동',
            s: n <= 3 ? '친구들이랑은 잘 지내요.' : '아빠가 밀어서 넘어진 적 있어요.',
            c: '94%',
          },
        ],
        diaryState: '확정',
        diaryCls: 'chip c-ok',
        diary:
          n <= 3
            ? '관계 형성 단계. 학교생활과 교우관계를 중심으로 대화함.'
            : '가정 내 체벌 경험을 처음 진술함. 진술 내용을 원문 그대로 기록함.',
        diaryBtn: '일지 수정',
        sumState: '확정',
        sumCls: 'chip c-ok',
        summary: n <= 3 ? '관계 형성 · 학교생활 중심.' : '가정 내 체벌 진술 · 원문 기록.',
        ai: n <= 3 ? '아동과 라포 형성 중. 특이 진술 없음.' : '아동이 보호자의 밀침 경험을 진술함.',
        sigs: n <= 3 ? [] : [['신체', '직접 신체 가해 · 01:00']],
      };

    const s = this.state;
    const r = getS(s.n);
    const proc = r.proc;
    const picks = [1, 2, 3, 4, 5, 6, 7, 8].map((n) => ({
      label: n + '회',
      on: n === s.n ? 'true' : 'false',
      bg: n === s.n ? '#E2ECF8' : '#FFFFFF',
      bd: n === s.n ? '#A8C6E7' : '#E7E0CE',
      fg: n === s.n ? '#2E5687' : '#2F3A44',
      fw: n === s.n ? 700 : 400,
      go: () => this.setState({ n }),
    }));
    const firstLine = r.lines[0] ? `${r.lines[0].t} "${r.lines[0].s}"` : '';
    const defs = proc
      ? [
          {
            href: '/SttReview',
            label: 'STT 검수',
            st: '진행 중 · 저신뢰 3곳',
            stCls: 'chip c-check',
            preview: '핵심 발화 4개 · ' + firstLine,
            cur: true,
          },
          {
            href: '/SignalReview',
            label: '위험 신호 검토',
            st: '대기',
            stCls: 'chip c-normal',
            preview: 'AI 신호 4개 · 신체 2 · 정서 1 · 방임 1',
          },
          {
            href: '/NoteWrite',
            label: '요약 · 일지 작성',
            st: '작성 전',
            stCls: 'chip c-normal',
            preview: '요약 · 일지 AI 초안 준비됨',
          },
          {
            href: '/FollowupQ',
            label: '추가 확인 · 질문',
            st: '대기',
            stCls: 'chip c-normal',
            preview: '확인 사항 3 · 추가 질문 5 (AI 초안)',
          },
        ]
      : [
          { href: '/SttReview', label: 'STT 검수', st: '검수 완료', stCls: 'chip c-ok', preview: firstLine },
          {
            href: '/SignalReview',
            label: '위험 신호 검토',
            st: r.sig,
            stCls: 'chip c-ok',
            preview: r.sigs.length ? r.sigs.map((g) => g[0] + ' · ' + g[1]).join('  /  ') : '채택 신호 없음',
          },
          {
            href: '/NoteWrite',
            label: '요약 · 일지 작성',
            st: '확정',
            stCls: 'chip c-ok',
            preview: r.summary,
          },
          {
            href: '/FollowupQ',
            label: '추가 확인 · 질문',
            st: '브리핑 반영',
            stCls: 'chip c-ok',
            preview: s.n + 1 + '회차 브리핑',
          },
        ];
    const steps = defs.map((d, i) => ({
      ...d,
      mark: !proc ? '✓' : String(i + 1),
      nBg: !proc ? '#F1EFE9' : d.cur ? '#A8C6E7' : '#EEE8DA',
      nFg: !proc ? '#55606A' : d.cur ? '#213F63' : '#6F7880',
      ring: d.cur ? 'inset 0 0 0 2px #A8C6E7' : 'none',
      bg: '#FFFFFF',
    }));
    return {
      picks,
      steps,
      cur: { no: s.n + '회차', meta: `${r.date} · ${r.kind} · 담당 이서연`, status: r.status, st: r.st },
    };
  }
}

export default function SessionDetail(props) {
  const v = useDC(Logic, props);
  return (
    <div className="pg-SessionDetail">
      <div
        style={{
          minHeight: '950px',
          background: '#FFFEFA',
          color: '#2F3A44',
          fontFamily: "'Noto Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'stretch',
        }}
      >
        <aside className="side" aria-label="주 메뉴">
          <A className="logo" to="/Main">
            <span className="mk">IS</span>
            <b style={{ fontSize: '17px' }}>I-SPOT</b>
          </A>
          <A className="cta" to="/UploadModal">
            ↑ 녹취 · 자료 올리기
          </A>
          <A className="cta2" to="/CaseRegister">
            + 새 사례 등록
          </A>
          <nav className="nav" aria-label="메뉴">
            <A to="/Main">홈</A>
            <A className="on" to="/CaseList">
              사례 관리
            </A>
            <A to="/Schedule">일정</A>
            <A to="/ChildLink">
              아이 연계<span className="cnt">4</span>
            </A>
            <A to="/Closure">
              종결 검토<span className="cnt">2</span>
            </A>
            <A to="/Stats">통계</A>
            <A to="/Settings">설정</A>
          </nav>
          <div className="me">
            <span className="av">이</span>
            <b style={{ fontWeight: '500' }}>이서연 상담원</b>
            <A to="/Login" className="note" style={{ marginLeft: 'auto' }}>
              로그아웃
            </A>
          </div>
        </aside>
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
          <nav aria-label="위치" className="note">
            <A to="/CaseList">사례 관리</A> › <A to="/CaseDetail">이서윤 C-2026-0351</A> ›{' '}
            <A to="/CaseHistory">상담 이력</A> › {v.cur.no}
          </nav>
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 300px' }}>
              <div className="sub">{v.cur.meta}</div>
              <h1 style={{ margin: '2px 0 0', fontSize: '30px', fontWeight: '700' }}>{v.cur.no} · 이서윤</h1>
            </div>
            <span className={v.cur.st} style={{ height: '28px' }}>
              {v.cur.status}
            </span>
          </header>
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
            <A className="btn btn-sm btn-s" to="/CaseHistory">
              ← 상담 이력
            </A>
            <span className="note" style={{ marginLeft: '6px' }}>
              다른 회차
            </span>
            {(v.picks || []).map((p, pIndex) => (
              <Fragment key={pIndex}>
                <button
                  type="button"
                  className="pick"
                  onClick={p.go}
                  aria-pressed={p.on}
                  style={{ background: p.bg, borderColor: p.bd, color: p.fg, fontWeight: p.fw }}
                >
                  {p.label}
                </button>
              </Fragment>
            ))}
          </section>
          <nav
            aria-label="회차 처리 단계"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
              gap: '18px',
            }}
          >
            {(v.steps || []).map((t, tIndex) => (
              <Fragment key={tIndex}>
                <A className="big" to={t.href} style={{ boxShadow: t.ring, background: t.bg }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    <span className="bn" style={{ background: t.nBg, color: t.nFg }}>
                      {t.mark}
                    </span>
                    <b style={{ flex: '1', fontSize: '20px' }}>{t.label}</b>
                    <span className={t.stCls}>{t.st}</span>
                  </span>
                  <span style={{ fontSize: '15px', lineHeight: '1.7' }}>{t.preview}</span>
                </A>
              </Fragment>
            ))}
          </nav>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
