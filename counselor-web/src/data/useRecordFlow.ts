// 사례 탭의 '녹음하기' 창 상태(사례 상세 · 상담 이력 · 문서함이 같이 쓴다, 10/29 디자인).
//
// 녹음은 창을 연 계정 · 사례의 것이다. 다른 탭에서 계정이 바뀌거나 다른 사례로 가거나 사례를 볼 수 없게 되면(403 등) 녹음을
// 버리고(마이크 끄기 · 들어 보기 주소 해제 · 올리기 멈춤) 창을 닫는다 — 앞 계정의 녹음을 새 계정이 듣거나 저장하지 않게.
// unsaved 는 화면을 떠날 때 물을지(useLeaveGuard)에 쓴다.
import { useEffect, useState } from "react";
import type { AuthSession } from "./useAuthSession";
import { type AudioRecorderState, useAudioRecorder } from "./useAudioRecorder";
import { type AudioUploadState, useAudioUpload } from "./useAudioUpload";

/** 실패해도 음성은 이미 서버에 있는 단계(원문 변환 요청 · 변환). 그 앞(회차 만들기 · 업로드)에서 실패하면 음성이 없다. */
const AUDIO_SAVED_STEPS = new Set(["requestStt", "transcribing"]);

/**
 * 녹음해 둔 것이 있어 닫거나 떠나면 사라지는가. 올리기 전, 그리고 음성을 서버에 올리기 전에 실패했으면 사라진다.
 * 올리는 중(회차 만들기 · 업로드 · 변환 요청)은 창 닫기를 막고 화면 이탈은 화면이 따로 묻는다.
 */
export function recordingUnsaved(recorder: Pick<AudioRecorderState, "status">, upload: Pick<AudioUploadState, "phase" | "failedStep">) {
  if (recorder.status === "idle") return false;
  if (upload.phase === "idle") return true;
  if (upload.phase === "failed") return !AUDIO_SAVED_STEPS.has(upload.failedStep ?? "");
  return false;
}

export function useRecordFlow(session: AuthSession, caseId: string | null, canRecord: boolean) {
  const [open, setOpen] = useState(false);
  const recorder = useAudioRecorder();
  const upload = useAudioUpload();
  const owner = session.status === "signedIn" && session.me && caseId ? `${session.me.id}|${caseId}` : null;
  const [recOwner, setRecOwner] = useState<string | null>(null);
  const stale = open && (owner === null || owner !== recOwner || !canRecord);
  const { reset: resetRecorder } = recorder;
  const { reset: resetUpload } = upload;

  useEffect(() => {
    if (!stale) return;
    resetRecorder();
    resetUpload();
    setOpen(false);
    setRecOwner(null);
  }, [stale, resetRecorder, resetUpload]);

  return {
    recorder,
    upload,
    show: open && !stale,
    canOpen: canRecord && owner !== null,
    start: () => {
      setRecOwner(owner);
      setOpen(true);
    },
    close: () => setOpen(false),
    unsaved: !stale && (recordingUnsaved(recorder, upload) || (upload.busy && upload.phase !== "transcribing")),
  };
}
