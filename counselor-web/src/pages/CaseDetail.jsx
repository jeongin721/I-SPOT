// 탭 1 · 내담자 정보 + 기관 서식 + 종결 검토 등록
// 원본: I-SPOT 디자인 캔버스 보드 CaseDetail.dc.html (자동 변환 후 다듬어 쓰세요)
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import './CaseDetail.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { reg: false };
  }
  renderVals() {
    return {
      isReg: this.state.reg,
      notReg: !this.state.reg,
      reg: () => this.setState({ reg: true }),
      unreg: () => this.setState({ reg: false }),
    };
  }
}

export default function CaseDetail(props) {
  const v = useDC(Logic, props);
  return (
    <div className="pg-CaseDetail">
      <div
        style={{
          minHeight: '1350px',
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
            <A to="/CaseList">사례 관리</A> › 이서윤 C-2026-0351
          </nav>
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '14px 18px' }}>
            <div style={{ flex: '1 1 320px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>이서윤</h1>
                <span className="sub">13세 · 중1</span>
                <span className="chip c-hi">위험도 상</span>
              </div>
              <div className="note">C-2026-0351 · 다음 상담 오늘 16:00</div>
            </div>
            <A className="btn btn-s" to="/UploadModal">
              ↑ 녹취 올리기
            </A>
          </section>
          <nav className="tabs" aria-label="사례 상세 메뉴">
            <A className="on" aria-current="page" to="/CaseDetail">
              내담자 정보
            </A>
            <A to="/CaseHistory">상담 이력</A>
            <A to="/PreBriefing">상담 전 브리핑</A>
            <A to="/CaseApp">아이 연계</A>
            <A to="/CaseDocs">문서함</A>
          </nav>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
              gap: '18px',
            }}
          >
            <section className="card" aria-label="기본 정보" style={{ padding: '22px 24px' }}>
              <h2 className="h2">기본 정보</h2>
              <dl className="kv" style={{ gridTemplateColumns: '120px 1fr' }}>
                <dt>개별사건번호</dt>
                <dd>C-2026-0351</dd>
                <dt>이름</dt>
                <dd>이서윤 (여)</dd>
                <dt>생년월일</dt>
                <dd>2013-03-14 (만 13세 · 중1)</dd>
                <dt>사례관리대상자</dt>
                <dd>이정훈 / 친부</dd>
                <dt>가족유형</dt>
                <dd>부자가정 · 원가정보호</dd>
                <dt>담당 상담원</dt>
                <dd>이서연</dd>
                <dt>신고접수일</dt>
                <dd>2026-07-28</dd>
                <dt>사례연계일</dt>
                <dd>2026-07-29</dd>
                <dt>상담 회차</dt>
                <dd style={{ fontWeight: '700' }}>8회</dd>
                <dt>최근 상담</dt>
                <dd>2026-10-02 · 방문상담</dd>
                <dt>아이 앱</dt>
                <dd>연결됨 (9/18) · 2주 응답 12/14</dd>
              </dl>
            </section>
            <section className="card" aria-label="주요 위험 요인" style={{ padding: '22px 24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2 className="h2">주요 위험 요인</h2>
                <span className="chip c-hi" style={{ marginLeft: 'auto' }}>
                  위험도 상
                </span>
              </div>
              <div className="note" style={{ marginTop: '4px', textAlign: 'right' }}>
                상담사 지정 · 9/18
              </div>
              <div className="note" style={{ marginTop: '10px' }}>
                학대 유형
              </div>
              <div style={{ margin: '6px 0 16px', display: 'flex', gap: '6px' }}>
                <span className="chip c-normal">신체</span>
                <span className="chip c-normal">정서</span>
                <span className="chip c-normal">방임 (확인 중)</span>
              </div>
              <div className="note">주요 키워드</div>
              <div style={{ marginTop: '6px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                <span className="chip c-normal">#체벌</span>
                <span className="chip c-normal">#두려움</span>
                <span className="chip c-normal">#진술압박</span>
                <span className="chip c-normal">#등·팔 통증</span>
                <span className="chip c-normal">#식사</span>
              </div>
              <div
                style={{
                  marginTop: '14px',
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <span className="note">사정결과</span>
                <b>집중관리</b>
                <span className="note">사정기록지 9/18</span>
              </div>
            </section>
          </div>
          <section className="card" aria-label="현재 진행 상황" style={{ padding: '22px 24px' }}>
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                gap: '8px',
                marginBottom: '16px',
              }}
            >
              <h2 className="h2">현재 진행 상황</h2>
              <span className="note">8회차 (10/2)</span>
              <A className="btn btn-p btn-sm" to="/SttReview" style={{ marginLeft: 'auto' }}>
                이어서 하기 · STT 검수
              </A>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <div
                style={{
                  minWidth: '660px',
                  display: 'grid',
                  gridTemplateColumns: 'repeat(5, minmax(0, 1fr))',
                  position: 'relative',
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    left: '10%',
                    right: '10%',
                    top: '17px',
                    height: '2px',
                    background: '#E7E0CE',
                  }}
                />
                <div className="st">
                  <span className="sd" style={{ background: '#F1EFE9', color: '#55606A' }}>
                    ✓
                  </span>
                  녹취 올림<span className="note">10/7</span>
                </div>
                <div className="st">
                  <span
                    className="sd"
                    style={{ background: '#FFFFFF', border: '2px solid #A8C6E7', color: '#2E5687' }}
                  >
                    1
                  </span>
                  <b style={{ fontWeight: '700', color: '#2E5687' }}>STT 검수</b>
                  <span className="chip c-check">저신뢰 3곳</span>
                </div>
                <div className="st">
                  <span className="sd" style={{ background: '#EEE8DA', color: '#6F7880' }}>
                    2
                  </span>
                  <span style={{ color: '#6F7880' }}>위험 신호 검토</span>
                </div>
                <div className="st">
                  <span className="sd" style={{ background: '#EEE8DA', color: '#6F7880' }}>
                    3
                  </span>
                  <span style={{ color: '#6F7880' }}>요약 · 일지 작성</span>
                </div>
                <div className="st">
                  <span className="sd" style={{ background: '#EEE8DA', color: '#6F7880' }}>
                    4
                  </span>
                  <span style={{ color: '#6F7880' }}>추가 확인 · 질문</span>
                </div>
              </div>
            </div>
            <div
              style={{
                marginTop: '18px',
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                gap: '12px',
              }}
            >
              <div className="box">
                <div className="note">아동 심리치료 (○○센터)</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span className="bar" style={{ flex: '1' }}>
                    <span style={{ width: '50%' }} />
                  </span>
                  <b>6 / 12회</b>
                </div>
              </div>
              <div className="box">
                <div className="note">보호자 부모교육</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span className="bar" style={{ flex: '1' }}>
                    <span style={{ width: '38%' }} />
                  </span>
                  <b>3 / 8회</b>
                </div>
              </div>
              <div className="box">
                <div className="note">다음 일정</div>
                <b style={{ fontWeight: '500' }}>오늘 16:00 · 9회차 정기상담</b>
                <div>
                  <A to="/PreBriefing" style={{ fontSize: '13px' }}>
                    상담 전 브리핑
                  </A>
                </div>
              </div>
            </div>
          </section>
          <section
            className="card"
            aria-label="기관 서식"
            style={{
              padding: '20px 24px',
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: '12px',
            }}
          >
            <b style={{ flex: '1 1 200px' }}>기관 서식</b>
            <span className="chip c-check">점검표 3차 작성 전</span>
            <A className="btn btn-p" to="/CaseForm">
              기관 서식 작성
            </A>
          </section>
          <section
            className="card"
            aria-label="종결 검토 등록"
            style={{
              padding: '20px 24px',
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: '12px',
            }}
          >
            <b style={{ flex: '1 1 200px' }}>종결 검토</b>
            {v.notReg ? (
              <>
                <button type="button" className="btn btn-y" onClick={v.reg}>
                  종결 검토 등록
                </button>
              </>
            ) : null}
            {v.isReg ? (
              <>
                <span className="chip c-ok">등록됨 · 초안 생성 중</span>
                <A className="btn btn-s" to="/Closure">
                  종결 검토 보기
                </A>
                <button type="button" className="btn btn-sm btn-s" onClick={v.unreg}>
                  등록 취소
                </button>
              </>
            ) : null}
          </section>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
