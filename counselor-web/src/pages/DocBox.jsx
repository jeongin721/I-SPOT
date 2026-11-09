// 문서함
// 원본: 11/05 디자인 '문서함 (폴더 · 문서 올리기 · 내려받기 · 정렬 · 첫 페이지 미리보기)' DocBox.dc.html.
//
// 서버 연결(2026-11-05): 기관 서식 · 참고 문서 공용 보관함(useDocBox, API_CONTRACT 23절). 화면 값은 src/data/screens/docBox.ts.
//  - 디자인 예시 문서 대신 서버 목록을 보인다. 마크업 · 클래스 · 문구는 디자인 그대로다.
//  - 올리기 · 폴더 만들기 · 옮기기는 서버에 저장하고, 내려받기는 서버 파일을 받는다. 그림 미리보기는 받은 파일로 보인다.
import { Navigate } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import Notice from '../components/Notice';
import NotiBell from '../components/NotiBell';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useDocBox } from '../data/useDocBox';
import { docBoxValues, initialDocBoxState } from '../data/screens/docBox';
import { needsLogin } from '../data/screens/common';
import { useTheme } from '../theme';
import './DocBox.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = initialDocBoxState();
  }
  renderVals() {
    return docBoxValues({ ...this.props, state: this.state, setState: (patch) => this.setState(patch) });
  }
}

export default function DocBox(props) {
  const session = useAuthSession();
  const theme = useTheme();
  const box = useDocBox(session);
  const v = useDC(Logic, { ...props, session, box });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-DocBox">
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
        <Sidebar active="DocBox" session={session} />
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
            <NotiBell session={session} />
            <ThemeToggle />
          </div>
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 260px' }}>
              <div className="sub">기관 서식 · 참고 문서 보관</div>
              <h1 style={{ margin: '2px 0 0', fontSize: '28px', fontWeight: '700' }}>문서함</h1>
            </div>
            <label className="btn btn-p" htmlFor="docbox-up" style={{ cursor: 'pointer' }}>
              ↑ 문서 올리기
            </label>
            <input
              id="docbox-up"
              type="file"
              multiple
              onChange={v.onUpload}
              style={{ position: 'absolute', width: '1px', height: '1px', opacity: '0', pointerEvents: 'none' }}
              aria-label="문서 올리기"
            />
          </header>
          <Notice value={v.notice} />
          {v.hasMsg ? (
            <p className="note" role="status" style={{ margin: '-8px 0 0', color: '#2B2A26' }}>
              {v.msg}
            </p>
          ) : null}

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '20px', alignItems: 'flex-start' }}>
            <section
              className="card"
              aria-label="폴더"
              style={{
                flex: '1 1 220px',
                maxWidth: '280px',
                padding: '14px',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', padding: '4px 6px 8px' }}>
                <h2 className="h2" style={{ fontSize: '15px' }}>
                  폴더
                </h2>
                <button type="button" className="btn btn-sm btn-s" style={{ marginLeft: 'auto' }} onClick={v.toggleNew}>
                  {v.newLabel}
                </button>
              </div>
              {v.adding ? (
                <div style={{ display: 'flex', gap: '6px', padding: '0 2px 8px' }}>
                  <input
                    className="inp"
                    type="text"
                    placeholder="새 폴더 이름"
                    aria-label="새 폴더 이름"
                    value={v.newName}
                    onChange={v.setNewName}
                    style={{ flex: '1', minWidth: '0', height: '36px' }}
                  />
                  <button type="button" className="btn btn-sm btn-p" onClick={v.addFolder}>
                    만들기
                  </button>
                </div>
              ) : null}
              {(v.folders || []).map((f, fIndex) => (
                <button key={fIndex} type="button" className={f.cls} aria-pressed={f.pressed} onClick={f.pick}>
                  <span className="fico" aria-hidden="true"></span>
                  <span>{f.name}</span>
                  <span className="n">{f.count}</span>
                </button>
              ))}
            </section>

            <section style={{ flex: '999 1 520px', minWidth: '0', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 12px' }}>
                <div style={{ flex: '1 1 200px' }}>
                  <span className="note">문서함</span>
                  <span className="note"> › </span>
                  <b>{v.curName}</b>
                  <span className="note" style={{ marginLeft: '8px' }}>
                    {v.shownCount}개
                  </span>
                </div>
                <div role="group" aria-label="정렬" className="seg">
                  <span className="seg-lb">정렬</span>
                  {(v.sorts || []).map((o, oIndex) => (
                    <button key={oIndex} type="button" className={o.cls} aria-pressed={o.pressed} onClick={o.pick}>
                      {o.label}
                    </button>
                  ))}
                </div>
              </div>
              {v.hasDocs ? (
                <div className="dgrid">
                  {(v.docs || []).map((d) => (
                    <article key={d.key} className="doc">
                      <div className="pv" role="img" aria-label={d.pvLabel}>
                        {d.isImg ? <img src={d.url} alt="" /> : null}
                        {d.isText ? (
                          <div className="pv-page">
                            <b>{d.pvTitle}</b>
                            {d.pvBody}
                          </div>
                        ) : null}
                        {d.isOther ? (
                          <div className="pv-other">
                            <span className="pv-ext">{d.ext}</span>
                            <span className="pv-lines">
                              <i></i>
                              <i style={{ width: '80%' }}></i>
                              <i></i>
                              <i style={{ width: '60%' }}></i>
                            </span>
                            <span className="note" style={{ fontSize: '11px' }}>
                              첫 페이지 미리보기를 만들 수 없는 형식
                            </span>
                          </div>
                        ) : null}
                      </div>
                      <div className="dname">{d.name}</div>
                      <div className="dmeta">{d.meta}</div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <button type="button" className="btn btn-sm btn-s" onClick={d.download}>
                          ↓ 내려받기
                        </button>
                        <select className="mv" aria-label={d.mvLabel} value={d.folder} onChange={d.move}>
                          {(d.opts || []).map((m) => (
                            <option key={m.id} value={m.id}>
                              {m.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    </article>
                  ))}
                </div>
              ) : null}
              {v.noDocs ? (
                <div className="empty">
                  이 폴더에는 아직 문서가 없어요 · ‘문서 올리기’로 추가하거나 다른 폴더의 문서를 옮겨 오세요
                </div>
              ) : null}
            </section>
          </div>
        </main>
      </div>
    </div>
  );
}
