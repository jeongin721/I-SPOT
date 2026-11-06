// 상담 이력 '새 상담 등록' 저장(screens/newSession.ts 머리 주석). 새 회차면 회차를 만들며 메모를 넣고, 있는 회차면 메모를 고친다.
import { useCallback, useState } from "react";
import { cases, sessions } from "../api/endpoints";
import { errorMessage } from "./useRemote";
import { NEW_SESSION } from "./screens/uploadModal";

export interface NewSessionState {
  saving: boolean;
  error: string | null;
  /** 저장한 회차 번호(확인창). */
  savedNumber: number | null;
  save: (caseId: string, target: string, memo: string) => Promise<boolean>;
  reset: () => void;
}

export function useNewSession(): NewSessionState {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNumber, setSavedNumber] = useState<number | null>(null);

  const save = useCallback(async (caseId: string, target: string, memo: string) => {
    setSaving(true);
    setError(null);
    try {
      const saved =
        target === NEW_SESSION ? await cases.createSession(caseId, { memo }) : await sessions.update(target, { memo });
      setSavedNumber(saved.session_number);
      return true;
    } catch (caught) {
      setError(errorMessage(caught, "상담 내용을 저장하지 못했습니다."));
      return false;
    } finally {
      setSaving(false);
    }
  }, []);

  const reset = useCallback(() => {
    setSaving(false);
    setError(null);
    setSavedNumber(null);
  }, []);

  return { saving, error, savedNumber, save, reset };
}
