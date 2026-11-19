// 문서함 화면 값(11/05 디자인 '문서함 · 폴더 · 문서 올리기 · 내려받기 · 정렬 · 첫 페이지 미리보기', 2026-11-05).
//
// 디자인의 동작(폴더 고르기 · 새 폴더 · 올리기 · 폴더 옮기기 · 날짜 · 이름 정렬 · 첫 페이지 미리보기)을 서버 문서함(useDocBox,
// API_CONTRACT 23절)으로 그린다. 디자인 예시 문서 대신 서버 목록을 보인다.
//  - 첫 페이지 미리보기: 그림은 그대로, 글(서버가 뽑은 앞부분)은 첫 줄을 제목으로, 그 밖은 형식 표시.
//  - 지우기는 관리자에게만 보이고, 확인 창을 거친다(디자인에 없어 사례 삭제 창의 틀을 쓴다).
//  - 올리기는 지금 고른 폴더에(전체 문서면 '폴더 없음'). 정렬 기본은 날짜 최신순(디자인과 같다 — 누르면 방향이 바뀐다).
//  - 빈 양식(11/09 디자인, src/data/blankForms.ts): 서버 문서가 아니라 화면에 들어 있는 6종이다. 옮기기 · 지우기가 없고,
//    입력한 내용은 저장하지 않는다. 11/17 디자인대로 서식 4종은 '기관 서식', 참고자료 2종은 '참고 자료' 폴더에 놓이고
//    전체 문서에도 함께 보이며 같이 정렬된다. 서버에 같은 이름의 폴더가 있으면 따로 만들지 않고 그 폴더에 함께 보인다
//    (그 폴더에서 올린 문서는 그 서버 폴더로 간다). 같은 이름의 서버 폴더가 없으면 화면에만 있는 폴더라, 거기서 올린 문서는
//    '폴더 없음' 으로 가고 전체 문서로 넘어가 보인다.
//  - 작성 양식 저장(2026-11-19): 빈 양식 창의 '저장' 은 제목 · 폴더를 정해 .ispotform 파일로 올린다. 고른 폴더가 화면에만 있는
//    빈 양식 폴더면 같은 이름의 서버 폴더를 만들어 거기에 둔다. 저장한 파일 카드의 '이어 쓰기' 는 내용을 받아 같은 창에 채운다.

import type { DocboxFile } from "../../api/types";
import { docbox } from "../../api/endpoints";
import {
  BLANK_FORM_DATE,
  BLANK_FORM_FOLDERS,
  BLANK_FORMS,
  FORM_FILE_EXT,
  blankFormById,
  downloadBlankForm,
  formFileText,
  formFileTitle,
  parseFormFile,
  type FormValues,
} from "../blankForms";
import type { BlankForm } from "../blankForms";
import type { AuthSession } from "../useAuthSession";
import type { DocBoxState } from "../useDocBox";
import { screenNotice } from "./common";

export interface DocBoxUiState {
  /** 'all' · 'none'(폴더 없음) · 'fixed:forms' · 'fixed:ref'(화면에만 있는 빈 양식 폴더) · 서버 폴더 id. */
  cur: string;
  /** 정렬. null 이면 날짜 최신순(디자인 기본). */
  pk: { k: "date" | "name"; first: boolean } | null;
  adding: boolean;
  newName: string;
  msg: string;
  /** 지우기 확인 창의 대상. */
  deleting: { id: string; name: string } | null;
  /** 열려 있는 빈 양식. 입력값은 창(BlankFormDialog)이 들고 있다. 저장한 파일을 열면 values · title 로 채운다. */
  form: { id: string; editing: boolean; values?: FormValues; title?: string; key?: string } | null;
}

export function initialDocBoxState(): DocBoxUiState {
  return { cur: "all", pk: null, adding: false, newName: "", msg: "", deleting: null, form: null };
}

interface DocBoxInput {
  session: AuthSession;
  box: DocBoxState;
  state: DocBoxUiState;
  setState: (patch: Partial<DocBoxUiState>) => void;
}

const NONE = "none";
/** 화면에만 있는 빈 양식 폴더 id 앞머리. 서버 폴더 id(UUID)와 겹치지 않는다. */
const FIXED = "fixed:";

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
  // 빈 양식 폴더(기관 서식 · 참고 자료). 서버에 같은 이름 폴더가 있으면 그 폴더 id 를 쓴다.
  const formFolders = BLANK_FORM_FOLDERS.map((g) => {
    const server = folderList.find((f) => f.name.trim() === g.name);
    return {
      id: server ? server.id : FIXED + g.id,
      name: g.name,
      forms: BLANK_FORMS.filter((f) => f.folder === g.id),
      serverCount: server ? server.count : 0,
    };
  });
  const formFolderOf = (id: string) => formFolders.find((g) => g.id === id) ?? null;
  const isFixed = (id: string) => id.startsWith(FIXED);
  const fname = (id: string | null) =>
    id === null
      ? "폴더 없음"
      : folderList.find((f) => f.id === id)?.name ?? formFolderOf(id)?.name ?? "폴더 없음";
  const inFolder = (file: DocboxFile) =>
    s.cur === "all" || (s.cur === NONE ? file.folder_id === null : file.folder_id === s.cur);

  const folders = [
    { id: "all", name: "전체 문서", count: files.length + BLANK_FORMS.length },
    ...formFolders.map((g) => ({ id: g.id, name: g.name, count: g.serverCount + g.forms.length })),
    ...folderList.filter((f) => !formFolderOf(f.id)),
  ].map((f) => ({
    name: f.name,
    count: f.count,
    cls: s.cur === f.id ? "fold on" : "fold",
    pressed: s.cur === f.id ? "true" : "false",
    pick: () => setState({ cur: f.id }),
  }));

  const pk = s.pk;
  const sk = pk ? pk.k : "date";
  const first = pk ? pk.first : true;
  const shownForms = s.cur === "all" ? BLANK_FORMS : formFolderOf(s.cur)?.forms ?? [];
  const list: { name: string; date: string; file?: DocboxFile; form?: BlankForm }[] = [
    ...shownForms.map((form) => ({ name: form.name, date: BLANK_FORM_DATE, form })),
    ...files.filter(inFolder).map((file) => ({ name: file.name, date: file.created_at, file })),
  ];
  list.sort((a, b) =>
    sk === "date"
      ? first
        ? b.date.localeCompare(a.date)
        : a.date.localeCompare(b.date)
      : first
        ? a.name.localeCompare(b.name, "ko", { numeric: true })
        : b.name.localeCompare(a.name, "ko", { numeric: true }),
  );

  const opts = [{ id: NONE, name: "폴더 없음" }, ...folderList.map((f) => ({ id: f.id, name: f.name }))];

  const formDoc = (form: BlankForm) => ({
    key: `form-${form.id}`,
    isForm: true,
    formId: form.id,
    name: form.name,
    meta: `${BLANK_FORM_DATE} · 작성 양식 · ${form.pages}쪽${s.cur === "all" ? " · " + (formFolders.find((g) => g.forms.includes(form))?.name ?? "") : ""}`,
    viewLabel: `${form.name} 내용 보기`,
    view: () => setState({ form: { id: form.id, editing: false } }),
    open: () => setState({ form: { id: form.id, editing: true } }),
    download: () =>
      setState({
        msg: downloadBlankForm(form) ? `‘${form.name}’ 내려받기를 시작했습니다` : "이 환경에서는 내려받기를 할 수 없습니다",
      }),
  });

  const fileDoc = (d: DocboxFile) => {
    const saved = extOf(d.name) === FORM_FILE_EXT.toUpperCase();
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
      // 작성 양식 파일: '이어 쓰기' 로 내용을 받아 빈 양식 창에 채운다.
      isSaved: saved,
      openSaved: async () => {
        const text = await box.readText(d.id);
        if (text === null) return;
        const parsed = parseFormFile(text);
        if (!parsed) return setState({ msg: `‘${d.name}’ 은(는) 열 수 없는 작성 양식 파일이에요` });
        setState({ form: { id: parsed.formId, editing: true, values: parsed.values, title: formFileTitle(d.name), key: d.id } });
      },
      canDelete: session.isAdmin,
      delLabel: `${d.name} 지우기`,
      askDelete: () => setState({ deleting: { id: d.id, name: d.name } }),
      download: async () => {
        if (await box.download(d.id, d.name)) setState({ msg: `‘${d.name}’ 내려받기를 시작했습니다` });
      },
      move: async (e: { target: { value: string } }) => {
        const v = e.target.value;
        const target = v === NONE ? null : v;
        if (box.busy || target === d.folder_id) return;
        if (await box.move(d.id, target)) setState({ msg: `‘${d.name}’을(를) ${fname(target)}(으)로 옮겼습니다` });
      },
    };
  };

  const docs = list.map((entry) => (entry.form ? formDoc(entry.form) : fileDoc(entry.file as DocboxFile)));

  const onUpload = async (e: { target: { files?: FileList | null; value: string } }) => {
    const picked = Array.from(e?.target?.files ?? []);
    try {
      e.target.value = "";
    } catch {
      /* 같은 파일을 다시 고를 수 있게 비운다 */
    }
    if (!picked.length || box.busy) return;
    const folder = s.cur === "all" || s.cur === NONE || isFixed(s.cur) ? null : s.cur;
    const count = await box.upload(picked, folder);
    // 화면에만 있는 빈 양식 폴더에서 올린 문서는 그 칸에 보이지 않으므로 전체 문서로 옮겨 보여 준다.
    if (count > 0) setState({ msg: `${count}개 문서를 ${fname(folder)}에 올렸습니다`, cur: isFixed(s.cur) ? "all" : s.cur });
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
    if (id) setState({ cur: id, adding: false, newName: "", msg: `‘${n}’ 폴더를 만들었습니다` });
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
  const openForm = s.form ? blankFormById(s.form.id) : null;
  // 저장할 폴더: 서버 폴더 + 화면에만 있는 빈 양식 폴더(고르면 저장할 때 같은 이름으로 만든다). 기본은 그 양식이 놓인 폴더.
  const saveFolders = [
    { id: "", name: "폴더 없음" },
    ...formFolders.map((g) => ({ id: g.id, name: g.name })),
    ...folderList.filter((f) => !formFolderOf(f.id)).map((f) => ({ id: f.id, name: f.name })),
  ];
  const homeFolder = openForm ? formFolders.find((g) => g.forms.includes(openForm))?.id ?? "" : "";

  return {
    openForm:
      openForm && s.form
        ? {
            id: openForm.id,
            key: s.form.key ?? openForm.id,
            name: openForm.name,
            editing: s.form.editing,
            values: s.form.values,
            title: s.form.title,
            folders: saveFolders,
            defaultFolder: homeFolder,
          }
        : null,
    editForm: () => setState({ form: s.form ? { ...s.form, editing: true } : null }),
    closeForm: () => setState({ form: null }),
    downloadForm: (values: FormValues) => {
      if (openForm) downloadBlankForm(openForm, values, s.form?.title);
    },
    saveForm: async ({ title, folderId, values }: { title: string; folderId: string | null; values: FormValues }) => {
      if (!openForm || box.busy) return false;
      let folder = folderId;
      let label = fname(folderId);
      if (folder && isFixed(folder)) {
        const name = formFolderOf(folder)?.name ?? "";
        let made = name ? await box.createFolder(name) : null;
        // 그사이 다른 분이 같은 이름 폴더를 만들었으면 409 — 목록을 다시 받아 그 폴더에 둔다(민규 리뷰 5).
        if (!made && name) {
          try {
            made = (await docbox.list()).folders.find((f) => f.name.trim() === name)?.id ?? null;
          } catch {
            made = null;
          }
        }
        if (!made) return false;
        folder = made;
        label = name;
      }
      const file = new File([formFileText(openForm.id, values)], `${title}.${FORM_FILE_EXT}`, { type: "application/json" });
      const count = await box.upload([file], folder);
      if (count > 0) setState({ msg: `‘${title}’ 을(를) ${label}에 저장했습니다` });
      return count > 0;
    },
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
