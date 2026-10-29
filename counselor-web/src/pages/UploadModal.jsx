// 녹취 · 자료 올리기 (팝업 3단계 + 확인창)
// 원본: 다솔 님 디자인 counselor-web-design/UploadModal.dc.html (front_new 브랜치)
//
// 서버 연결: 화면 주소 ?case=…(&session=…) 로 열면 그 사례(회차)를 고른 채 시작한다. 사례 목록은 useCaseList,
// 고른 사례의 회차는 useCaseDetail, 올리기 · 원문 변환은 useAudioUpload 가 하고, 화면에 쓸 값은
// src/data/screens/uploadModal.ts 가 만든다. 이 파일은 훅을 부르고 배치만 한다.
// 끝나면 확인창에서 그 회차의 STT 검수(이동) 또는 회차 상세(나중에)로 간다. ?back= 으로 열었으면 닫기 · 취소 · 나중에는 그 화면으로.
// 10/21 디자인(counselor-design/screens/UploadModal.dc.html): 회차 목록 스크롤 · 새 회차 맨 위 · 고른 파일 '빼기' · 돌아갈 곳.
import { Fragment, useState } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useAudioUpload } from '../data/useAudioUpload';
import { useCaseDetail } from '../data/useCaseDetail';
import { useCaseList } from '../data/useCaseList';
import { needsLogin, signedIn } from '../data/screens/common';
import { readBackHref, readScreenIds } from '../data/screens/links';
import { initialUploadState, uploadModalValues } from '../data/screens/uploadModal';
import './UploadModal.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = initialUploadState(props.ids);
  }
  renderVals() {
    return uploadModalValues({ ...this.props, state: this.state, setState: (patch) => this.setState(patch) });
  }
}

export default function UploadModal(props) {
  const [params] = useSearchParams();
  const ids = readScreenIds(params);
  // 주소의 사례 · 회차가 바뀌면 처음부터 다시 그린다(고른 사례 · 단계를 앞 주소 것으로 두고 올리지 않게).
  return (
    <UploadModalScreen key={`${ids.caseId ?? ''}|${ids.sessionId ?? ''}`} {...props} ids={ids} back={readBackHref(params)} />
  );
}

function UploadModalScreen(props) {
  const { ids } = props;
  const session = useAuthSession();
  const go = useNavigate();
  const enabled = signedIn(session);
  const [search, setSearch] = useState('');
  const [caseId, setCaseId] = useState(ids.caseId);
  const list = useCaseList({ search, enabled });
  const caseDetail = useCaseDetail(caseId, { enabled });
  const upload = useAudioUpload();
  const theme = useTheme();
  const v = useDC(Logic, {
    ...props,
    session,
    ids,
    list,
    search,
    setSearch,
    caseId,
    setCaseId,
    caseDetail,
    upload,
    go,
  });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-UploadModal">
      <div
        className={theme.cls}
        style={{
          minHeight: '1000px',
          background: 'rgba(47,58,68,0.40)',
          fontFamily: "'IBM Plex Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          color: '#2B2A26',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '48px 16px',
          position: 'relative',
        }}
      >
        <div className="thm-abs">
          <ThemeToggle />
        </div>
        <section
          role="dialog"
          aria-modal="true"
          aria-labelledby="up-title"
          style={{
            width: '100%',
            maxWidth: '640px',
            background: '#FFFFFF',
            borderRadius: '24px',
            boxShadow: '0 20px 60px rgba(43, 42, 38,0.22)',
            overflow: 'hidden',
          }}
        >
          <div style={{ padding: '24px 30px 18px', borderBottom: '1px solid #EAE7DF' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <h1 id="up-title" style={{ margin: '0', fontSize: '20px', fontWeight: '700' }}>
                녹취 · 자료 올리기
              </h1>
              <A
                to={v.closeHref}
                aria-label="닫기"
                style={{
                  marginLeft: 'auto',
                  width: '40px',
                  height: '40px',
                  borderRadius: '50%',
                  background: '#F7F6F2',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  textDecoration: 'none',
                  color: '#2B2A26',
                  fontSize: '18px',
                }}
              >
                ×
              </A>
            </div>
            <ol
              aria-label="업로드 단계"
              style={{
                listStyle: 'none',
                margin: '14px 0 0',
                padding: '0',
                display: 'flex',
                flexWrap: 'wrap',
                gap: '6px',
              }}
            >
              {(v.steps || []).map((s, sIndex) => (
                <Fragment key={sIndex}>
                  <li
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '6px 12px 6px 6px',
                      borderRadius: '999px',
                      fontSize: '13px',
                      background: s.bg,
                      color: s.fg,
                      fontWeight: s.fw,
                    }}
                  >
                    <span
                      style={{
                        width: '22px',
                        height: '22px',
                        borderRadius: '50%',
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '12px',
                        fontWeight: '700',
                        background: s.dotBg,
                        color: s.dotFg,
                      }}
                    >
                      {s.mark}
                    </span>
                    {s.label}
                  </li>
                </Fragment>
              ))}
            </ol>
          </div>
          <div style={{ padding: '24px 30px', minHeight: '360px' }}>
            {v.s1 ? (
              <>
                <p className="lb">어느 아이의 자료인가요?</p>
                <input
                  className="inp"
                  type="search"
                  aria-label="이름 또는 사례 ID 검색"
                  placeholder="이름 또는 사례 ID 검색"
                  style={{ width: '100%' }}
                  {...v.search}
                />
                <div
                  style={{
                    marginTop: '12px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px',
                    maxHeight: '320px',
                    overflowY: 'auto',
                    paddingRight: '6px',
                  }}
                >
                  {(v.cases || []).map((c, cIndex) => (
                    <Fragment key={cIndex}>
                      <button
                        type="button"
                        className="opt"
                        onClick={c.pick}
                        style={{ borderColor: c.bd, background: c.bg, font: 'inherit', textAlign: 'left' }}
                      >
                        <span
                          style={{
                            width: '18px',
                            height: '18px',
                            borderRadius: '50%',
                            border: `2px solid ${c.dot}`,
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: c.fill }}></span>
                        </span>
                        <span>
                          <b style={{ fontWeight: '500' }}>{c.name}</b> <span className="note">{c.meta}</span>
                        </span>
                      </button>
                    </Fragment>
                  ))}
                  {v.casesNote ? (
                    <p className="note" role="status" style={{ margin: 0 }}>
                      {v.casesNote}
                    </p>
                  ) : null}
                </div>
                <div
                  style={{
                    marginTop: '16px',
                    padding: '14px 16px',
                    borderRadius: '14px',
                    border: '1px dashed #DAD5C9',
                    display: 'flex',
                    flexWrap: 'wrap',
                    alignItems: 'center',
                    gap: '10px',
                  }}
                >
                  <span style={{ flex: '1 1 240px', fontSize: '13px' }}>찾는 아이가 없나요?</span>
                  <A className="btn btn-sm btn-s" to={v.registerHref}>
                    + 새 사례 등록
                  </A>
                </div>
              </>
            ) : null}
            {v.s2 ? (
              <>
                <div
                  style={{ padding: '12px 16px', borderRadius: '14px', background: '#F7F6F2', marginBottom: '16px' }}
                >
                  <b style={{ fontWeight: '500' }}>{v.caseName}</b>
                </div>
                <p className="lb">몇 회차 상담인가요?</p>
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px',
                    maxHeight: '320px',
                    overflowY: 'auto',
                    paddingRight: '6px',
                  }}
                >
                  {(v.sessions || []).map((x, xIndex) => (
                    <Fragment key={xIndex}>
                      <button
                        type="button"
                        className="opt"
                        onClick={x.pick}
                        style={{ borderColor: x.bd, background: x.bg, font: 'inherit', textAlign: 'left' }}
                      >
                        <span
                          style={{
                            width: '18px',
                            height: '18px',
                            borderRadius: '50%',
                            border: `2px solid ${x.dot}`,
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: x.fill }}></span>
                        </span>
                        <span>
                          <b style={{ fontWeight: '500' }}>{x.label}</b>
                          <span className="note" style={{ display: 'block' }}>
                            {x.meta}
                          </span>
                        </span>
                      </button>
                    </Fragment>
                  ))}
                  {v.sessionsNote ? (
                    <p className="note" role="status" style={{ margin: 0 }}>
                      {v.sessionsNote}
                    </p>
                  ) : null}
                </div>
              </>
            ) : null}
            {v.s3 ? (
              <>
                <div
                  style={{ padding: '12px 16px', borderRadius: '14px', background: '#F7F6F2', marginBottom: '16px' }}
                >
                  <b style={{ fontWeight: '500' }}>{v.caseName}</b> · {v.sesLabel}
                </div>
                <p className="lb">파일 선택</p>
                <label
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '26px',
                    borderRadius: '16px',
                    border: '1.5px dashed #DAD5C9',
                    background: '#F7F6F2',
                    cursor: 'pointer',
                    textAlign: 'center',
                  }}
                >
                  <span
                    style={{
                      width: '52px',
                      height: '52px',
                      borderRadius: '50%',
                      background: '#F2EFE8',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#66625A',
                      fontSize: '22px',
                      fontWeight: '700',
                    }}
                  >
                    ↑
                  </span>
                  <b style={{ fontWeight: '500' }}>파일을 끌어 놓거나 눌러서 선택</b>
                  <input
                    key={v.fileKey}
                    type="file"
                    aria-label="파일 선택"
                    accept={v.accept}
                    onChange={v.pickFile}
                    style={{ fontSize: '13px', marginTop: '6px' }}
                  />
                </label>
                {v.hasFile ? (
                  <div
                    style={{
                      marginTop: '12px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      padding: '10px 14px',
                      borderRadius: '12px',
                      border: '1px solid #E7E4DC',
                    }}
                  >
                    <span className="chip c-sky">음성</span>
                    <span style={{ flex: '1', minWidth: '0', overflowWrap: 'anywhere' }}>{v.fileName}</span>
                    <span className="note">{v.fileMeta}</span>
                    <button
                      type="button"
                      className="btn btn-sm btn-s"
                      onClick={v.clearFile}
                      aria-label="선택한 파일 빼기"
                    >
                      빼기
                    </button>
                  </div>
                ) : null}
                {v.fileError ? (
                  <p className="note" role="alert" style={{ margin: '8px 0 0', color: '#A33B2E' }}>
                    {v.fileError}
                  </p>
                ) : null}
                <div style={{ marginTop: '14px', display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
                  <div className="fmt">
                    <b style={{ fontSize: '13px' }}>음성 파일</b>
                    <span className="note">{v.audioRule}</span>
                  </div>
                  <div className="fmt">
                    <b style={{ fontSize: '13px' }}>문서 파일</b>
                    <span className="note">{v.docRule}</span>
                  </div>
                </div>
              </>
            ) : null}
          </div>
          <div
            style={{
              padding: '18px 30px 24px',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              borderTop: '1px solid #EAE7DF',
            }}
          >
            {v.s1 ? (
              <>
                <A className="btn btn-s" to={v.closeHref}>
                  취소
                </A>
              </>
            ) : null}
            {v.notFirst ? (
              <>
                <button type="button" className="btn btn-s" onClick={v.prev}>
                  이전
                </button>
              </>
            ) : null}
            <span style={{ flex: '1' }}></span>
            {v.notLast ? (
              <>
                <button type="button" className="btn btn-p" onClick={v.next} disabled={!v.canNext}>
                  다음
                </button>
              </>
            ) : null}
            {v.s3 ? (
              <>
                <button type="button" className="btn btn-p" onClick={v.upload} disabled={!v.canUpload}>
                  업로드
                </button>
              </>
            ) : null}
          </div>
        </section>

        {v.confirm ? (
          <>
            <div
              style={{
                position: 'absolute',
                inset: '0',
                background: 'rgba(47,58,68,0.30)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '16px',
              }}
            >
              <section
                role="alertdialog"
                aria-labelledby="ok-title"
                style={{
                  width: '100%',
                  maxWidth: '440px',
                  background: '#FFFFFF',
                  borderRadius: '22px',
                  boxShadow: '0 20px 60px rgba(43, 42, 38,0.28)',
                  padding: '28px 28px 22px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                }}
              >
                <span
                  style={{
                    width: '48px',
                    height: '48px',
                    borderRadius: '50%',
                    background: '#F2EFE8',
                    color: '#66625A',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '22px',
                    fontWeight: '700',
                  }}
                >
                  {v.dialogMark}
                </span>
                <h2 id="ok-title" style={{ margin: '0', fontSize: '20px', fontWeight: '700' }}>
                  {v.dialogTitle}
                </h2>
                <p style={{ margin: '0' }} aria-live="polite">
                  {v.dialogText}
                  <br />
                  <b>{v.dialogAsk}</b>
                </p>
                <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '6px' }}>
                  {(v.dialogActions || []).map((a, aIndex) => (
                    <button
                      key={aIndex}
                      type="button"
                      className={`btn ${a.primary ? 'btn-p' : 'btn-s'}`}
                      onClick={a.onClick}
                      disabled={a.disabled}
                    >
                      {a.label}
                    </button>
                  ))}
                </div>
              </section>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
