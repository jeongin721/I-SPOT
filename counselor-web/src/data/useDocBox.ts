// 문서함 훅(GET /docbox · POST /docbox/folders · POST /docbox/files · PATCH /docbox/files/{id} · 내려받기, API_CONTRACT 23절, 2026-11-05).
//
// 목록(폴더 · 문서)을 한 번에 부르고, 쓰기(폴더 만들기 · 올리기 · 옮기기)는 끝나면 조용히 다시 부른다.
// 그림 미리보기는 파일 본체를 받아 blob 주소로 보인다(로그인 토큰이 필요해 <img src> 에 API 주소를 바로 쓰지 못한다).

import { useCallback, useEffect, useRef, useState } from "react";

import { docbox } from "../api/endpoints";
import type { DocboxList } from "../api/types";
import type { AuthSession } from "./useAuthSession";
import { errorMessage, useRemote } from "./useRemote";

export interface DocBoxState {
  data: DocboxList | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
  busy: boolean;
  /** 쓰기 · 내려받기 실패 문구(서버 문구). */
  actionError: string | null;
  /** 그림 문서의 blob 주소(id → url). 받는 중이거나 못 받으면 없다. */
  imageUrls: Record<string, string>;
  createFolder: (name: string) => Promise<string | null>;
  upload: (files: File[], folderId: string | null) => Promise<number>;
  move: (fileId: string, folderId: string | null) => Promise<boolean>;
  download: (fileId: string, name: string) => Promise<boolean>;
}

export function useDocBox(session: AuthSession): DocBoxState {
  const me = session.status === "signedIn" ? session.me : null;
  const key = me ? `docbox:${me.id}` : null;
  const remote = useRemote<DocboxList>(key, () => docbox.list(), "문서함을 불러오지 못했습니다.", () => false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [imageUrls, setImageUrls] = useState<Record<string, string>>({});
  const urls = useRef<Record<string, string>>({});

  const run = useCallback(
    async <T,>(work: () => Promise<T>, fallback: string): Promise<T | null> => {
      setBusy(true);
      setActionError(null);
      try {
        const result = await work();
        remote.refresh();
        return result;
      } catch (caught) {
        setActionError(errorMessage(caught, fallback));
        return null;
      } finally {
        setBusy(false);
      }
    },
    [remote],
  );

  // 그림 문서만 본체를 받아 미리보기 주소를 만든다. 목록에서 빠진 것은 주소를 풀어 준다.
  const files = remote.data?.files;
  useEffect(() => {
    if (!files) return;
    const controller = new AbortController();
    const wanted = new Set(files.filter((file) => file.preview_kind === "image").map((file) => file.id));
    for (const id of Object.keys(urls.current)) {
      if (!wanted.has(id)) {
        URL.revokeObjectURL(urls.current[id]);
        delete urls.current[id];
      }
    }
    setImageUrls({ ...urls.current });
    wanted.forEach((id) => {
      if (urls.current[id]) return;
      docbox
        .file(id, controller.signal)
        .then((blob) => {
          if (controller.signal.aborted) return;
          urls.current[id] = URL.createObjectURL(blob);
          setImageUrls({ ...urls.current });
        })
        .catch(() => undefined);
    });
    return () => controller.abort();
  }, [files]);

  useEffect(
    () => () => {
      Object.values(urls.current).forEach((url) => URL.revokeObjectURL(url));
      urls.current = {};
    },
    [],
  );

  const createFolder = useCallback(
    async (name: string) => (await run(() => docbox.createFolder(name), "폴더를 만들지 못했습니다."))?.id ?? null,
    [run],
  );
  const upload = useCallback(
    async (list: File[], folderId: string | null) =>
      (await run(() => docbox.upload(list, folderId), "문서를 올리지 못했습니다."))?.files.length ?? 0,
    [run],
  );
  const move = useCallback(
    async (fileId: string, folderId: string | null) =>
      (await run(() => docbox.move(fileId, folderId), "문서를 옮기지 못했습니다.")) !== null,
    [run],
  );
  const download = useCallback(async (fileId: string, name: string) => {
    setActionError(null);
    try {
      const blob = await docbox.file(fileId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = name;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 4000);
      return true;
    } catch (caught) {
      setActionError(errorMessage(caught, "문서를 내려받지 못했습니다."));
      return false;
    }
  }, []);

  return {
    data: remote.data,
    loading: remote.loading,
    error: remote.error,
    reload: remote.reload,
    busy,
    actionError,
    imageUrls,
    createFolder,
    upload,
    move,
    download,
  };
}
