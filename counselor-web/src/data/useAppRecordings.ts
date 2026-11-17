// 상담사 앱(폰) 화면들이 같이 쓰는 녹음 대기열 상태. 로그인한 계정의 줄만 보이고, 바뀌면(같은 탭 · 다른 탭) 다시 읽는다.
// 처음 붙을 때 끊긴 녹음을 되살리고(recoverDrafts) 실패한 줄까지 다시 올리기 시작한다(앱을 다시 연 경우).

import { useCallback, useEffect, useState } from "react";

import { CONSULTATION_TYPE_LABELS, type ConsultationType } from "../api/types";
import { purgeLegacyMemos } from "./appOffline";
import {
  cleanOrphanChunks,
  listRecordings,
  processQueue,
  recoverDrafts,
  setKindTitle,
  setQueueUser,
  subscribeRecordings,
  type RecordingItem,
} from "./appRecordings";
import { activeDraftId } from "./useRecorder";

const kindLabel = (type: ConsultationType) => CONSULTATION_TYPE_LABELS[type] ?? type;

setKindTitle(kindLabel);

/** 이 탭에서 처음 한 번만 실패한 줄까지 다시 올린다(화면을 옮길 때마다 되풀이하지 않게). */
let resumedFor: string | null = null;

export function useAppRecordings(userId: string | null): { items: RecordingItem[]; loaded: boolean; storageError: boolean } {
  const [items, setItems] = useState<RecordingItem[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [storageError, setStorageError] = useState(false);

  const load = useCallback(() => {
    if (!userId) return;

    listRecordings(userId)
      .then((rows) => {
        setItems(rows);
        setLoaded(true);
        setStorageError(false);
      })
      .catch(() => {
        setLoaded(true);
        setStorageError(true);
      });
  }, [userId]);

  useEffect(() => {
    setQueueUser(userId);

    if (!userId) {
      setItems([]);
      return undefined;
    }

    const unsubscribe = subscribeRecordings(load);

    load();

    if (resumedFor !== userId) {
      resumedFor = userId;
      purgeLegacyMemos();
      recoverDrafts(userId, activeDraftId(), kindLabel)
        .catch(() => {})
        .then(() => cleanOrphanChunks(activeDraftId()))
        .catch(() => {})
        .finally(() => void processQueue(true));
    }

    // 앱을 켜 둔 동안 1분마다 연결 끊김 · 서버 오류로 실패한 줄을 다시 올려 본다(online 이벤트가 오지 않는 경우: 서버가 잠깐 꺼짐 등).
    const timer = window.setInterval(() => {
      if (navigator.onLine !== false) void processQueue(true);
    }, 60_000);

    return () => {
      unsubscribe();
      window.clearInterval(timer);
    };
  }, [userId, load]);

  return { items, loaded, storageError };
}

export { kindLabel };
