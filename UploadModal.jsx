// 녹취 · 자료 올리기 (팝업 3단계 + 확인창)
// 원본: I-SPOT 디자인 캔버스 보드 UploadModal.dc.html (자동 변환 후 다듬어 쓰세요)
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import './UploadModal.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { step: 1, c: 0, x: 0, confirm: false };
  }
  renderVals() {
    const s = this.state;
    const labels = ['사례 선택', '상담 회차', '파일 선택'];
    const steps = labels.map((label, i) => {
      const n = i + 1,
        done = n < s.step,
        cur = n === s.step;
      return {
        label,
        mark: done ? '✓' : String(n),
        bg: cur ? '#E2ECF8' : 'transparent',
        fg: cur ? '#2E5687' : done ? '#2F3A44' : '#6F7880',
        fw: cur ? 700 : 400,
        dotBg: cur ? '#A8C6E7' : done ? '#F1EFE9' : '#EEE8DA',
        dotFg: cur ? '#213F63' : done ? '#55606A' : '#6F7880',
      };
    });
    const cs = [
      ['이서윤', 'C-2026-0351 · 8회차까지 진행'],
      ['김도현', 'C-2026-0412 · 6회차까지 진행'],
      ['박지호', 'C-2026-0389 · 3회차까지 진행'],
    ];
    const radio = (on) => ({
      bd: on ? '#A8C6E7' : '#E7E0CE',
      bg: on ? '#E2ECF8' : '#FFFFFF',
      dot: on ? '#2E5687' : '#DCD5C3',
      fill: on ? '#2E5687' : 'transparent',
    });
    const cases = cs.map((c, i) => ({
      name: c[0],
      meta: c[1],
      ...radio(i === s.c),
      pick: () => this.setState({ c: i }),
    }));
    const xs = [
      ['8회차 · 10/2 방문상담', '녹취 아직 없음'],
      ['새 회차 · 9회차', '새로 등록'],
      ['7회차 · 9/18 정기상담', '녹취 있음 · 추가 자료'],
    ];
    const sessions = xs.map((x, i) => ({
      label: x[0],
      meta: x[1],
      ...radio(i === s.x),
      pick: () => this.setState({ x: i }),
    }));
    return {
      steps,
      cases,
      sessions,
      caseName: cs[s.c][0] + ' · ' + cs[s.c][1].split(' · ')[0],
      sesLabel: xs[s.x][0].split(' · ')[0],
      s1: s.step === 1,
      s2: s.step === 2,
      s3: s.step === 3,
      notFirst: s.step > 1,
      notLast: s.step < 3,
      confirm: s.confirm,
      next: () => this.setState({ step: Math.min(3, s.step + 1) }),
      prev: () => this.setState({ step: Math.max(1, s.step - 1) }),
      upload: () => this.setState({ confirm: true }),
    };
  }
}

export default function UploadModal(props) {
  const v = useDC(Logic, props);
  return (
    <div className="pg-UploadModal">
      <div
        style={{
          minHeight: '1000px',
          background: 'rgba(47,58,68,0.40)',
          fontFamily: "'Noto Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          color: '#2F3A44',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '48px 16px',
          position: 'relative',
        }}
      >
        <section
          role="dialog"
          aria-modal="true"
          aria-labelledby="up-title"
          style={{
            width: '100%',
            maxWidth: '640px',
            background: '#FFFFFF',
            borderRadius: '24px',
            boxShadow: '0 20px 60px rgba(30,50,80,0.22)',
            overflow: 'hidden',
          }}
        >
          <div style={{ padding: '24px 30px 18px', borderBottom: '1px solid #EEE8DA' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <h1 id="up-title" style={{ margin: '0', fontSize: '20px', fontWeight: '700' }}>
                녹취 · 자료 올리기
              </h1>
              <A
                to="/Main"
                aria-label="닫기"
                style={{
                  marginLeft: 'auto',
                  width: '40px',
                  height: '40px',
                  borderRadius: '50%',
                  background: '#F8F5EC',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  textDecoration: 'none',
                  color: '#2F3A44',
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
                />
                <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
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
                          <span
                            style={{ width: '8px', height: '8px', borderRadius: '50%', background: c.fill }}
                          />
                        </span>
                        <span>
                          <b style={{ fontWeight: '500' }}>{c.name}</b> <span className="note">{c.meta}</span>
                        </span>
                      </button>
                    </Fragment>
                  ))}
                </div>
                <div
                  style={{
                    marginTop: '16px',
                    padding: '14px 16px',
                    borderRadius: '14px',
                    border: '1px dashed #DCD5C3',
                    display: 'flex',
                    flexWrap: 'wrap',
                    alignItems: 'center',
                    gap: '10px',
                  }}
                >
                  <span style={{ flex: '1 1 240px', fontSize: '13px' }}>찾는 아이가 없나요?</span>
                  <A className="btn btn-sm btn-s" to="/CaseRegister">
                    + 새 사례 등록
                  </A>
                </div>
              </>
            ) : null}
            {v.s2 ? (
              <>
                <div
                  style={{
                    padding: '12px 16px',
                    borderRadius: '14px',
                    background: '#F8F5EC',
                    marginBottom: '16px',
                  }}
                >
                  <b style={{ fontWeight: '500' }}>{v.caseName}</b>
                </div>
                <p className="lb">몇 회차 상담인가요?</p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
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
                          <span
                            style={{ width: '8px', height: '8px', borderRadius: '50%', background: x.fill }}
                          />
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
                </div>
              </>
            ) : null}
            {v.s3 ? (
              <>
                <div
                  style={{
                    padding: '12px 16px',
                    borderRadius: '14px',
                    background: '#F8F5EC',
                    marginBottom: '16px',
                  }}
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
                    border: '1.5px dashed #DCD5C3',
                    background: '#F8F5EC',
                    cursor: 'pointer',
                    textAlign: 'center',
                  }}
                >
                  <span
                    style={{
                      width: '52px',
                      height: '52px',
                      borderRadius: '50%',
                      background: '#F1EFE9',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#55606A',
                      fontSize: '22px',
                      fontWeight: '700',
                    }}
                  >
                    ↑
                  </span>
                  <b style={{ fontWeight: '500' }}>파일을 끌어 놓거나 눌러서 선택</b>
                  <input type="file" aria-label="파일 선택" style={{ fontSize: '13px', marginTop: '6px' }} />
                </label>
                <div
                  style={{
                    marginTop: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '10px 14px',
                    borderRadius: '12px',
                    border: '1px solid #E7E0CE',
                  }}
                >
                  <span className="chip c-sky">음성</span>
                  <span style={{ flex: '1' }}>방문상담_1002.m4a</span>
                  <span className="note">24분 · 18MB</span>
                </div>
                <div style={{ marginTop: '14px', display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
                  <div className="fmt">
                    <b style={{ fontSize: '13px' }}>음성 파일</b>
                    <span className="note">MP3 · M4A · WAV · 최대 2시간</span>
                  </div>
                  <div className="fmt">
                    <b style={{ fontSize: '13px' }}>문서 파일</b>
                    <span className="note">PDF · HWPX · DOCX · TXT</span>
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
              borderTop: '1px solid #EEE8DA',
            }}
          >
            {v.s1 ? (
              <>
                <A className="btn btn-s" to="/Main">
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
            <span style={{ flex: '1' }} />
            {v.notLast ? (
              <>
                <button type="button" className="btn btn-p" onClick={v.next}>
                  다음
                </button>
              </>
            ) : null}
            {v.s3 ? (
              <>
                <button type="button" className="btn btn-p" onClick={v.upload}>
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
                  boxShadow: '0 20px 60px rgba(30,50,80,0.28)',
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
                    background: '#F1EFE9',
                    color: '#55606A',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '22px',
                    fontWeight: '700',
                  }}
                >
                  ✓
                </span>
                <h2 id="ok-title" style={{ margin: '0', fontSize: '20px', fontWeight: '700' }}>
                  업로드했어요
                </h2>
                <p style={{ margin: '0' }}>
                  {v.caseName} · {v.sesLabel} · 방문상담_1002.m4a
                  <br />
                  STT 분석 시작 · <b>검수 화면으로 이동할까요?</b>
                </p>
                <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '6px' }}>
                  <A className="btn btn-s" to="/Main">
                    나중에
                  </A>
                  <A className="btn btn-p" to="/SttReview">
                    이동
                  </A>
                </div>
              </section>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
