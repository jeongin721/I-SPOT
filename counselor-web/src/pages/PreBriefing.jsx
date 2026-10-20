// 탭 3 · 상담 전 브리핑 (+ 신변안전 확인)
// 원본: 다솔 님 디자인 counselor-web-design/PreBriefing.dc.html (front_new 브랜치). 화면 값은 아직 예시(가상) 데이터다.
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useCarryHref } from '../data/useCarryHref';
import { useTheme } from '../theme';
import './PreBriefing.css';

class Logic extends DCLogic {
  renderVals() {
    return {};
  }
}

export default function PreBriefing(props) {
  // 사이드바의 내 정보 · 로그아웃 · '관리자 메뉴'(관리자일 때만)에만 쓴다. 이 화면의 값은 아직 예시 데이터다.
  const session = useAuthSession();
  const carry = useCarryHref();
  const theme = useTheme();
  const v = useDC(Logic, props);
  return (
    <div className="pg-PreBriefing">
      <div
        className={theme.cls}
        style={{
          minHeight: '1550px',
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
        <Sidebar active="CaseList" session={session} />
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
          <nav aria-label="위치" className="note">
            <A to="/CaseList">사례 관리</A> › 이서윤 C-2026-0351
          </nav>
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '14px 18px' }}>
            <A className="btn btn-sm btn-s" to="/CaseList">
              ← 목록
            </A>
            <div style={{ flex: '1 1 320px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>이서윤</h1>
                <span className="sub">13세 · 중1</span>
                <span className="chip c-hi">위험도 상</span>
              </div>
              <div className="note">C-2026-0351 · 다음 상담 오늘 16:00</div>
            </div>
            <A className="btn btn-s" to={carry('/UploadModal')}>
              ↑ 녹취 올리기
            </A>
          </section>
          <nav className="tabs" aria-label="사례 상세 메뉴">
            <A to={carry('/CaseDetail')}>내담자 정보</A>
            <A to={carry('/CaseHistory')}>상담 이력</A>
            <A className="on" aria-current="page" to={carry('/PreBriefing')}>
              상담 전 브리핑
            </A>
            <A to={carry('/CaseApp')}>아이 연계</A>
            <A to={carry('/CaseDocs')}>문서함</A>
          </nav>
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 20px' }}>
            <div style={{ flex: '1 1 380px' }}>
              <div className="sub">오늘 16:00 · 9회차 정기상담 · 면담실 B</div>
              <h2 style={{ margin: '2px 0 0', fontSize: '22px', fontWeight: '700' }}>상담 전 브리핑</h2>
            </div>
            <button type="button" className="btn btn-s">
              인쇄 · PDF
            </button>
          </section>

          <section
            aria-label="먼저 볼 것"
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px' }}
          >
            <div
              className="card"
              style={{ padding: '18px 20px', display: 'flex', flexDirection: 'column', gap: '4px' }}
            >
              <span className="note">아이가 보낸 말</span>
              <b style={{ fontWeight: '500' }}>"다음 상담 때 말할 게 있어요"</b>
              <span className="src">10/7 22:10 · 아이 앱</span>
            </div>
            <div
              className="card"
              style={{ padding: '18px 20px', display: 'flex', flexDirection: 'column', gap: '4px' }}
            >
              <span className="note">체크인 응답 변화</span>
              <span>
                겁을 준 적 있어? <b>없어 → 1번</b>
              </span>
              <span className="src">10/6 · QB-E-05</span>
            </div>
            <div
              className="card"
              style={{ padding: '18px 20px', display: 'flex', flexDirection: 'column', gap: '4px' }}
            >
              <span className="note">처음 나온 이야기</span>
              <span>식사 · 돌봄 — "밥도 안 줄 때가 있어요"</span>
              <span className="src">8회차 02:15 · 화자 확인 중</span>
            </div>
          </section>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '18px' }}>
            <section
              className="card"
              style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '10px' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2 className="h2">확인할 사항</h2>
                <span className="chip c-ai">AI 초안</span>
              </div>
              <label className="rq">
                <input type="checkbox" defaultChecked />
                <span>
                  등 · 팔 통증 치료 여부<span className="src">근거 · 8회차 01:08</span>
                </span>
              </label>
              <label className="rq">
                <input type="checkbox" defaultChecked />
                <span>
                  02:15 발화 화자 · 식사 상황<span className="src">근거 · 8회차 02:15</span>
                </span>
              </label>
              <label className="rq">
                <input type="checkbox" />
                <span>
                  아이가 꺼내고 싶은 이야기부터<span className="src">근거 · 10/7 아이 메시지</span>
                </span>
              </label>
            </section>
            <section
              className="card"
              style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '10px' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2 className="h2">추가 질문</h2>
                <span className="chip c-ai">AI 초안</span>
                <A to={carry('/FollowupQ')} style={{ marginLeft: 'auto', fontSize: '13px' }}>
                  질문 수정
                </A>
              </div>
              <div className="rq">
                <span className="chip c-normal">열린 질문</span>
                <span>"등이랑 팔이 아팠던 건 지금은 어때? 누가 봐 준 적 있어?"</span>
              </div>
              <div className="rq">
                <span className="chip c-normal">열린 질문</span>
                <span>"그 이야기를 하면 어떤 일이 생길 것 같아?"</span>
              </div>
              <div className="rq">
                <span className="chip c-normal">QB-N-01</span>
                <span>"요즘 밥은 주로 어떻게 먹어?"</span>
              </div>
            </section>
          </div>

          <section
            className="card"
            aria-label="신변안전 확인"
            style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '10px' }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
              <h2 className="h2 acc">신변안전 확인</h2>
              <span className="chip c-normal">8회차 방문 중 대상자 귀가</span>
              <span className="src" style={{ marginLeft: 'auto' }}>
                매뉴얼 5장
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '10px' }}>
              <label className="rq">
                <input type="checkbox" defaultChecked />
                <span>
                  기관 면담실 B에서 진행<span className="src">근거 · 8회차 03:05</span>
                </span>
              </label>
              <label className="rq">
                <input type="checkbox" />
                <span>가정방문 시 2인 1조 · 방문지 · 복귀 시간 보고</span>
              </label>
              <label className="rq">
                <input type="checkbox" />
                <span>열린 공간 · 문 가까이 착석 · 동거인 확인</span>
              </label>
              <label className="rq">
                <input type="checkbox" />
                <span>대상자 음주 시 면접 종료 · 일지 기록</span>
              </label>
            </div>
            <p className="note" style={{ margin: '0' }}>
              자살 · 살해 발언 시 112 · 자살예방센터 · 정신건강복지센터 신고
            </p>
          </section>

          <section className="card" style={{ padding: '22px 24px' }}>
            <h2 className="h2" style={{ marginBottom: '12px' }}>
              그대로 남겨 둔 진술
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '10px' }}>
              <div style={{ padding: '12px 14px', borderRadius: '12px', background: '#F7F6F2' }}>
                <span className="src">6회차 05:02</span>
                <div>"맞은 적은… 잘 모르겠어요"</div>
              </div>
              <div style={{ padding: '12px 14px', borderRadius: '12px', background: '#F7F6F2' }}>
                <span className="src">8회차 00:41</span>
                <div>"소리 지르고… 많이 때렸어요"</div>
              </div>
            </div>
          </section>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
