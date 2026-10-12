// 설정 · 계정 / 알림 설정
// 원본: I-SPOT 디자인 캔버스 보드 Settings.dc.html (자동 변환 후 다듬어 쓰세요)
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import './Settings.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = {
      view: 'home',
      name: '이서연',
      mail: 'lee.seoyeon@ispot-center.kr',
      edit: null,
      draft: '',
      mailSent: false,
      pw: false,
      t: { urgent: true, brief: true, done: false },
      batch: '09:00',
    };
  }
  renderVals() {
    const s = this.state;
    const sw = (on) => ({
      bg: on ? '#A8C6E7' : '#DCD5C3',
      x: on ? '23px' : '3px',
      on: on ? 'true' : 'false',
    });
    const defs = [
      ['urgent', '긴급 응답 즉시 알림'],
      ['brief', '상담 30분 전 브리핑 알림'],
      ['done', 'STT 분석 완료 알림'],
    ];
    const toggles = defs.map(([k, label]) => ({
      label,
      ...sw(s.t[k]),
      flip: () => this.setState({ t: { ...s.t, [k]: !s.t[k] } }),
    }));
    const titles = { home: '설정', account: '계정', notify: '알림 설정' };
    return {
      title: titles[s.view],
      subTitle: titles[s.view],
      atHome: s.view === 'home',
      inSub: s.view !== 'home',
      isAccount: s.view === 'account',
      isNotify: s.view === 'notify',
      goHome: () => this.setState({ view: 'home', edit: null }),
      goAccount: () => this.setState({ view: 'account' }),
      goNotify: () => this.setState({ view: 'notify' }),
      name: s.name,
      mail: s.mail,
      draft: s.draft,
      mailSent: s.mailSent,
      nameView: s.edit !== 'name',
      nameEdit: s.edit === 'name',
      mailView: s.edit !== 'mail',
      mailEdit: s.edit === 'mail',
      editName: () => this.setState({ edit: 'name', draft: s.name }),
      editMail: () => this.setState({ edit: 'mail', draft: s.mail, mailSent: false }),
      setDraft: (e) => this.setState({ draft: e.target.value }),
      cancel: () => this.setState({ edit: null }),
      saveName: () => this.setState({ edit: null, name: s.draft || s.name }),
      saveMail: () => this.setState({ edit: null, mailSent: true }),
      pwText: s.pw ? '재설정 링크 발송됨 · 30분 유효' : '마지막 변경 2026-08-12',
      pwLabel: s.pw ? '다시 보내기' : '비밀번호 재설정',
      pwCls: s.pw ? 'btn-s' : 'btn-p',
      resetPw: () => this.setState({ pw: true }),
      toggles,
      urgentOff: !s.t.urgent,
      batch: s.batch,
      setBatch: (e) => this.setState({ batch: e.target.value }),
    };
  }
}

export default function Settings(props) {
  const v = useDC(Logic, props);
  return (
    <div className="pg-Settings">
      <div
        style={{
          minHeight: '800px',
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
            <A to="/CaseList">사례 관리</A>
            <A to="/Schedule">일정</A>
            <A to="/ChildLink">
              아이 연계<span className="cnt">4</span>
            </A>
            <A to="/Closure">
              종결 검토<span className="cnt">2</span>
            </A>
            <A to="/Stats">통계</A>
            <A className="on" to="/Settings">
              설정
            </A>
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
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 300px' }}>
              <nav aria-label="위치" className="note">
                {v.inSub ? (
                  <>
                    <A to="/Settings">설정</A> › {v.subTitle}
                  </>
                ) : null}
                {v.atHome ? <>설정</> : null}
              </nav>
              <h1 style={{ margin: '2px 0 0', fontSize: '28px', fontWeight: '700' }}>{v.title}</h1>
            </div>
            {v.inSub ? (
              <>
                <button type="button" className="btn btn-s" onClick={v.goHome}>
                  ← 설정
                </button>
              </>
            ) : null}
          </header>
          {v.atHome ? (
            <>
              <section
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
                  gap: '18px',
                  maxWidth: '900px',
                }}
              >
                <button type="button" className="pick" onClick={v.goAccount}>
                  <b style={{ fontSize: '20px' }}>계정</b>
                </button>
                <button type="button" className="pick" onClick={v.goNotify}>
                  <b style={{ fontSize: '20px' }}>알림 설정</b>
                </button>
              </section>
            </>
          ) : null}
          {v.isAccount ? (
            <>
              <section
                className="card"
                aria-label="계정"
                style={{ padding: '6px 26px 14px', maxWidth: '900px' }}
              >
                <div className="row">
                  <span className="lab">상담사 이름</span>
                  {v.nameView ? (
                    <>
                      <b style={{ flex: '1', fontWeight: '500' }}>{v.name}</b>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.editName}>
                        수정
                      </button>
                    </>
                  ) : null}
                  {v.nameEdit ? (
                    <>
                      <input
                        className="edit-in"
                        type="text"
                        aria-label="상담사 이름"
                        value={v.draft}
                        onChange={v.setDraft}
                      />
                      <button type="button" className="btn btn-sm btn-p" onClick={v.saveName}>
                        저장
                      </button>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.cancel}>
                        취소
                      </button>
                    </>
                  ) : null}
                </div>
                <div className="row">
                  <span className="lab">계정 (연결된 이메일)</span>
                  {v.mailView ? (
                    <>
                      <b style={{ flex: '1', fontWeight: '500' }}>{v.mail}</b>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.editMail}>
                        변경
                      </button>
                    </>
                  ) : null}
                  {v.mailEdit ? (
                    <>
                      <input
                        className="edit-in"
                        type="email"
                        aria-label="이메일"
                        value={v.draft}
                        onChange={v.setDraft}
                      />
                      <button type="button" className="btn btn-sm btn-p" onClick={v.saveMail}>
                        인증 메일 보내기
                      </button>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.cancel}>
                        취소
                      </button>
                    </>
                  ) : null}
                </div>
                <div className="row">
                  <span className="lab">비밀번호</span>
                  <span style={{ flex: '1' }} className="sub">
                    {v.pwText}
                  </span>
                  <button type="button" className={`btn btn-sm ${v.pwCls}`} onClick={v.resetPw}>
                    {v.pwLabel}
                  </button>
                </div>
                <div className="row" style={{ borderBottom: '0' }}>
                  <span className="lab">소속 기관</span>
                  <b style={{ flex: '1', fontWeight: '500' }}>○○아동보호전문기관</b>
                </div>
              </section>
              {v.mailSent ? (
                <>
                  <p className="note" style={{ margin: '0' }}>
                    인증 메일 발송됨
                  </p>
                </>
              ) : null}
            </>
          ) : null}
          {v.isNotify ? (
            <>
              <section
                className="card"
                aria-label="알림 설정"
                style={{ padding: '6px 26px 14px', maxWidth: '900px' }}
              >
                {(v.toggles || []).map((t, tIndex) => (
                  <Fragment key={tIndex}>
                    <div className="row">
                      <b style={{ flex: '1', fontWeight: '500' }}>{t.label}</b>
                      <button
                        type="button"
                        className="sw"
                        role="switch"
                        aria-checked={t.on}
                        aria-label={t.label}
                        onClick={t.flip}
                        style={{ background: t.bg }}
                      >
                        <span style={{ left: t.x }} />
                      </button>
                    </div>
                  </Fragment>
                ))}
                <div className="row" style={{ borderBottom: '0' }}>
                  <b style={{ flex: '1', fontWeight: '500' }}>아이 체크인 묶음 시간</b>
                  <select className="inp" aria-label="묶음 시간" value={v.batch} onChange={v.setBatch}>
                    <option>08:30</option>
                    <option>09:00</option>
                    <option>13:00</option>
                    <option>17:00</option>
                  </select>
                </div>
              </section>
              {v.urgentOff ? (
                <>
                  <p className="acc" style={{ margin: '0', fontSize: '13px', fontWeight: '500' }}>
                    긴급 응답 알림 꺼짐 · 아이의 긴급 응답을 바로 알 수 없어요
                  </p>
                </>
              ) : null}
            </>
          ) : null}
        </main>
      </div>
    </div>
  );
}
