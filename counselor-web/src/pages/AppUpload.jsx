// 상담사 앱(폰) · 업로드
// 원본: 앱 · 업로드 (사진 찍기 · 파일 선택 · 실패 시 다시 올리기) 2026-11-10 zip 의 AppUpload.dc.html
//
// 서버 연결
//  - 올린 자료: 이 폰의 녹음 대기열(appRecordings.ts). 올리는 중 · 실패 · 완료를 보이고, 실패하면 '다시 올리기' 로 실패한 단계부터
//    다시 올린다(새 회차를 이미 만들었으면 다시 만들지 않는다). '지우기' 는 폰에서만 지운다(서버에 올라간 것은 그대로).
//  - 자료 올리기 › 파일: 음성 파일(.m4a · .mp3 · .wav 등)이면 고른 아이의 새 회차로 올리고 원문 변환까지 요청한다.
//  - 목록을 열 때 다 올린 줄의 회차를 서버에 물어, 웹에서 지웠거나(404) 볼 수 없게 된(403) 회차는 목록에서 뺀다.
//  - 주소에 ?case= 가 있으면 그 아이를 골라 둔다(앱 사례 목록의 '자료 올리기').
//  - 사진 · 문서는 사례에 붙일 서버 자리(사례 파일함)가 아직 없어 '준비 중' 안내만 보인다.
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import MobileAppShell, { sizeText, whenText, whoText } from '../components/MobileAppShell';
import { childLabelOf, useAppCases } from '../data/useAppCases';
import { enqueueAudioFile, removeRecording, retryRecording, syncDoneWithServer, uploadAsNewSession } from '../data/appRecordings';
import { checkAudioFile, readAudioDuration } from '../data/audioFile';

function UploadBody({ userId, items, notReady }) {
  const my = useAppCases(userId);
  const rows = my.rows;
  const [params] = useSearchParams();
  const [picked, setCaseId] = useState(params.get('case') ?? '');
  const caseId = rows.some((row) => row.id === picked) ? picked : rows[0]?.id ?? '';
  const [pk, setPk] = useState(false);

  // 목록을 열 때 다 올린 줄을 서버와 맞춘다(웹에서 지운 회차는 뺀다).
  useEffect(() => {
    if (userId) void syncDoneWithServer(userId).catch(() => {});
  }, [userId]);
  const [pickErr, setPickErr] = useState('');

  const child = rows.find((row) => row.id === caseId);
  const fails = items.filter((x) => x.status === 'fail');
  const stop = (ev) => ev.stopPropagation();

  const pickFile = async (ev) => {
    const fl = ev?.target?.files?.[0];
    try {
      ev.target.value = '';
    } catch {
      // 일부 브라우저
    }
    if (!fl) return;
    setPk(false);
    setPickErr('');
    const isAudio = /^audio\//.test(fl.type) || /\.(m4a|mp3|wav|ogg|flac|webm|mp4)$/i.test(fl.name);
    if (!isAudio) {
      notReady('사진 · 문서 올리기');
      return;
    }
    const problem = checkAudioFile(fl);
    if (problem) {
      setPickErr(problem);
      return;
    }
    if (!child || !userId) {
      setPickErr('아이를 먼저 골라 주세요.');
      return;
    }
    const durationMs = await readAudioDuration(fl);
    try {
      await enqueueAudioFile({ userId, caseId: child.id, childLabel: childLabelOf(child), file: fl, durationMs });
    } catch {
      setPickErr('폰에 파일을 저장하지 못했어요. 저장 공간을 확인해 주세요.');
    }
  };

  return (
    <>
      <label className="ma-fl">
        <span className="ma-lb">사례 아동 선택</span>
        <select className="ma-inp" value={caseId} onChange={(ev) => setCaseId(ev.target.value)} disabled={rows.length === 0}>
          {rows.length === 0 && <option value="">{my.loading ? '불러오는 중' : '담당 사례 없음'}</option>}
          {rows.map((row) => (
            <option key={row.id} value={row.id}>
              {childLabelOf(row)}
            </option>
          ))}
        </select>
      </label>
      <button type="button" className="ma-pk ma-pk1" onClick={() => setPk(true)}>
        <span className="ma-pk-i">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 15V4M7 9l5-5 5 5"></path><path d="M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"></path></svg>
        </span>
        자료 올리기<span className="ma-note" style={{ fontWeight: 400 }}>파일 · 사진 보관함 · 사진 찍기</span>
      </button>
      {(pickErr || my.error) && <span className="ma-err">{pickErr || my.error}</span>}
      <p className="ma-sec-t">
        올린 자료 <span className="ma-note">· 실패 {fails.length}건</span>
      </p>
      {items.length === 0 && <span className="ma-note">아직 올린 자료가 없어요. 녹음을 저장하면 여기에 보여요.</span>}
      {items.map((x) => {
        const run = x.status === 'run' || x.status === 'wait';
        const fail = x.status === 'fail';
        return (
          <div key={x.id} className={fail ? 'ma-card ma-qi ma-f' : 'ma-card ma-qi'}>
            <div className="ma-qi-top">
              <span className="ma-chip">녹음</span>
              <span style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '2px' }}>
                <b>{x.fileName}</b>
                <span className="ma-note">
                  {whoText(x)} · {sizeText(x.size)} · {whenText(x.status === 'done' ? x.updatedAt : x.createdAt)}
                </span>
              </span>
              <span className={fail ? 'ma-chip ma-red' : run ? 'ma-chip ma-gold' : 'ma-chip'}>{fail ? '실패' : run ? '올리는 중' : '완료'}</span>
            </div>
            {run && (
              <div className="ma-prog">
                <span></span>
              </div>
            )}
            {fail && (
              <>
                <span style={{ fontSize: '13.5px', color: 'var(--red)' }}>{x.error}</span>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '8px' }}>
                  <button
                    type="button"
                    className="ma-btn ma-btn-sm ma-btn-red"
                    onClick={() => {
                      if (window.confirm('이 녹음을 폰에서 지울까요? 아직 서버에 올라가지 않은 녹음은 되살릴 수 없어요.')) void removeRecording(x.id);
                    }}
                  >
                    지우기
                  </button>
                  <button
                    type="button"
                    className="ma-btn ma-btn-sm ma-btn-p"
                    onClick={() => void (x.needNewSession ? uploadAsNewSession(x.id) : retryRecording(x.id))}
                  >
                    {x.needNewSession ? '새 회차로 올리기' : '다시 올리기'}
                  </button>
                </div>
              </>
            )}
          </div>
        );
      })}
      {pk && (
        <div className="ma-ov" onClick={() => setPk(false)}>
          <section className="ma-sheet" role="dialog" aria-modal="true" aria-label="자료 올리기" onClick={stop}>
            <span className="ma-grab" aria-hidden="true"></span>
            <div className="ma-sh-hd">
              <b>자료 올리기</b>
              <button type="button" className="ma-btn ma-btn-sm" onClick={() => setPk(false)}>
                닫기
              </button>
            </div>
            <div className="ma-pko">
              <label className="ma-pkr">
                <span className="ma-pk-i">
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 3h10l4 4v14H5z"></path><path d="M9 11h6M9 15h6"></path></svg>
                </span>
                <span className="ma-pkr-t">
                  <b>파일</b>
                </span>
                <input type="file" aria-label="휴대폰 파일에서 고르기" onChange={pickFile} />
              </label>
              <label className="ma-pkr">
                <span className="ma-pk-i">
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"></rect><circle cx="9" cy="10" r="2"></circle><path d="M21 16l-5-5-9 9"></path></svg>
                </span>
                <span className="ma-pkr-t">
                  <b>사진 보관함</b>
                </span>
                <input type="file" accept="image/*" aria-label="사진 보관함에서 고르기" onChange={pickFile} />
              </label>
              <label className="ma-pkr">
                <span className="ma-pk-i">
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 8h3l2-3h6l2 3h3v11H4z"></path><circle cx="12" cy="13" r="3.5"></circle></svg>
                </span>
                <span className="ma-pkr-t">
                  <b>사진 찍기</b>
                </span>
                <input type="file" accept="image/*" capture="environment" aria-label="사진 찍어 올리기" onChange={pickFile} />
              </label>
            </div>
          </section>
        </div>
      )}
    </>
  );
}

export default function AppUpload() {
  return (
    <MobileAppShell cur="up" sub="사진 · 문서 · 음성 파일" title="업로드">
      {(ctx) => <UploadBody {...ctx} />}
    </MobileAppShell>
  );
}
