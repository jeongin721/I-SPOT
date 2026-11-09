// 문서함 화면 값(11/05 디자인 '문서함 · 폴더 · 문서 올리기 · 내려받기 · 정렬 · 첫 페이지 미리보기', 2026-11-05).
//
// 디자인의 동작(폴더 고르기 · 새 폴더 · 올리기 · 폴더 옮기기 · 날짜 · 이름 정렬 · 첫 페이지 미리보기)을 서버 문서함(useDocBox,
// API_CONTRACT 23절)으로 그린다. 디자인 예시 문서 대신 서버 목록을 보인다.
//  - 첫 페이지 미리보기: 그림은 그대로, 글(서버가 뽑은 앞부분)은 첫 줄을 제목으로, 그 밖은 형식 표시.
//  - 지우기는 관리자에게만 보이고, 확인 창을 거친다(디자인에 없어 사례 삭제 창의 틀을 쓴다).
//  - 올리기는 지금 고른 폴더에(전체 문서면 '폴더 없음'). 정렬 기본은 날짜 최신순(디자인과 같다 — 누르면 방향이 바뀐다).

import type { DocboxFile } from "../../api/types";
import type { AuthSession } from "../useAuthSession";
import type { DocBoxState } from "../useDocBox";
import { screenNotice } from "./common";

export interface DocBoxUiState {
  /** 'all' · 'none'(폴더 없음) · 폴더 id. */
  cur: string;
  /** 정렬. null 이면 날짜 최신순(디자인 기본). */
  pk: { k: "date" | "name"; first: boolean } | null;
  adding: boolean;
  newName: string;
  msg: string;
  /** 지우기 확인 창의 대상. */
  deleting: { id: string; name: string } | null;
}

export function initialDocBoxState(): DocBoxUiState {
  return { cur: "all", pk: null, adding: false, newName: "", msg: "", deleting: null };
}

interface DocBoxInput {
  session: AuthSession;
  box: DocBoxState;
  state: DocBoxUiState;
  setState: (patch: Partial<DocBoxUiState>) => void;
}

const NONE = "none";

function fmtSize(n: number): string {
  return n < 1024 ? `${n}B` : n < 1048576 ? `${Math.round(n / 102.4) / 10}KB` : `${Math.round(n / 104857.6) / 10}MB`;
}

function ymd(iso: string): string {
  const d = new Date(iso);
  const p = (x: number) => String(x).padStart(2, "0");
  return Number.isNaN(d.getTime()) ? "" : `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function extOf(name: string): string {
  const m = /\.([^.]+)$/.exec(name);
  return m ? m[1].toUpperCase() : "FILE";
}

export function docBoxValues(input: DocBoxInput) {
  const { session, box, state: s, setState } = input;
  const data = box.data;
  const folderList = data?.folders ?? [];
  const files = data?.files ?? [];
  const fname = (id: string | null) =>
    id === null ? "폴더 없음" : folderList.find((f) => f.id === id)?.name ?? "폴더 없음";
  const inFolder = (file: DocboxFile) =>
    s.cur === "all" || (s.cur === NONE ? file.folder_id === null : file.folder_id === s.cur);

  const folders = [{ id: "all", name: "전체 문서", count: files.length }, ...folderList].map((f) => ({
    name: f.name,
    count: f.count,
    cls: s.cur === f.id ? "fold on" : "fold",
    pressed: s.cur === f.id ? "true" : "false",
    pick: () => setState({ cur: f.id }),
  }));

  const pk = s.pk;
  const sk = pk ? pk.k : "date";
  const first = pk ? pk.first : true;
  let list = files.filter(inFolder);
  list =
    sk === "date"
      ? list.slice().sort((a, b) => (first ? b.created_at.localeCompare(a.created_at) : a.created_at.localeCompare(b.created_at)))
      : list.slice().sort((a, b) => (first ? a.name.localeCompare(b.name, "ko") : b.name.localeCompare(a.name, "ko")));

  const opts = [{ id: NONE, name: "폴더 없음" }, ...folderList.map((f) => ({ id: f.id, name: f.name }))];

  const docs = list.map((d) => {
    const lines = (d.preview_text ?? "").split("\n");
    const url = box.imageUrls[d.id] ?? "";
    const isImg = d.preview_kind === "image" && !!url;
    const isText = d.preview_kind === "text";
    const by = d.uploaded_by_name ? ` · ${d.uploaded_by_name}` : "";
    return {
      key: d.id,
      name: d.name,
      folder: d.folder_id ?? NONE,
      ext: extOf(d.name),
      url,
      isImg,
      isText,
      isOther: !isImg && !isText,
      pvTitle: lines[0] || d.name,
      pvBody: lines.slice(1, 22).join("\n"),
      pvLabel: `${d.name} 첫 페이지 미리보기`,
      meta: `${ymd(d.created_at)} · ${fmtSize(d.size_bytes)} · ${extOf(d.name)}${s.cur === "all" ? " · " + fname(d.folder_id) : ""}${by}`,
      opts,
      mvLabel: `${d.name} 폴더 옮기기`,
      canDelete: session.isAdmin,
      delLabel: `${d.name} 지우기`,
      askDelete: () => setState({ deleting: { id: d.id, name: d.name } }),
      download: async () => {
        if (await box.download(d.id, d.name)) setState({ msg: `‘${d.name}’ 내려받기를 시작했어요` });
      },
      move: async (e: { target: { value: string } }) => {
        const v = e.target.value;
        const target = v === NONE ? null : v;
        if (box.busy || target === d.folder_id) return;
        if (await box.move(d.id, target)) setState({ msg: `‘${d.name}’을(를) ${fname(target)}(으)로 옮겼어요` });
      },
    };
  });

  const onUpload = async (e: { target: { files?: FileList | null; value: string } }) => {
    const picked = Array.from(e?.target?.files ?? []);
    try {
      e.target.value = "";
    } catch {
      /* 같은 파일을 다시 고를 수 있게 비운다 */
    }
    if (!picked.length || box.busy) return;
    const folder = s.cur === "all" || s.cur === NONE ? null : s.cur;
    const count = await box.upload(picked, folder);
    if (count > 0) setState({ msg: `${count}개 문서를 ${fname(folder)}에 올렸어요` });
  };

  const sorts = (
    [
      ["date", "날짜"],
      ["name", "이름"],
    ] as const
  ).map(([v, l]) => {
    const on = !!pk && pk.k === v;
    return {
      label: on ? l + (first ? "↑" : "↓") : l,
      cls: on ? "on" : "",
      pressed: on ? "true" : "false",
      pick: () => setState({ pk: on ? { k: v, first: !first } : { k: v, first: true } }),
    };
  });

  const addFolder = async () => {
    const n = s.newName.trim();
    if (!n || box.busy) return;
    const id = await box.createFolder(n);
    if (id) setState({ cur: id, adding: false, newName: "", msg: `‘${n}’ 폴더를 만들었어요` });
  };

  const target = s.deleting;
  const closeDelete = () => {
    if (!box.busy) setState({ deleting: null });
  };
  const confirmDelete = async () => {
    if (!target || box.busy) return;
    const done = await box.remove(target.id);
    // 실패하면 창을 닫고 서버 문구를 화면의 안내 줄에 보인다.
    setState(done ? { deleting: null, msg: `‘${target.name}’을(를) 지웠어요` } : { deleting: null });
  };

  const curName = s.cur === "all" ? "전체 문서" : s.cur === NONE ? "폴더 없음" : fname(s.cur);
  const msg = box.actionError ?? (box.busy ? "처리하는 중…" : s.msg);

  return {
    notice: screenNotice({ session, loading: box.loading && !data, error: box.error, retry: box.reload }),
    folders,
    docs,
    hasDocs: docs.length > 0,
    noDocs: docs.length === 0,
    shownCount: docs.length,
    curName,
    sorts,
    onUpload,
    adding: s.adding,
    newName: s.newName,
    newLabel: s.adding ? "닫기" : "+ 새 폴더",
    toggleNew: () => setState({ adding: !s.adding, newName: "" }),
    setNewName: (e: { target: { value: string } }) => setState({ newName: e.target.value }),
    addFolder,
    deleting: target,
    delBusy: box.busy,
    closeDelete,
    confirmDelete,
    hasMsg: !!msg,
    msg,
  };
}
