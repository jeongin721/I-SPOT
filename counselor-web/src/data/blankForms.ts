// 문서함의 빈 양식(11/09 디자인 '문서함 작성 양식', 2026-11-09).
//
// 디자인의 작성 양식 6종을 화면에서 보여 주고 채운다. 채운 값은 '저장' 을 눌러야 문서함에 작성 양식 파일(.ispotform, JSON —
// formFileText)로 남고(2026-11-19), 내려받기는 적은 내용이 든 HTML 이다. 브라우저 저장소에는 넣지 않는다.
// 이 양식에는 아동 이름 · 생년월일 칸이 있는데 문서함은 모든 상담원에게 보이므로, 저장 창에서 '아이를 알아볼 수 있는 정보 없음'
// 확인을 받는다. 사례에 남기는 작성은 지금처럼 사례 상세 › 문서함(API_CONTRACT 22절)에서 한다.

import { BLANK_FORM_DEFS } from "./blankFormDefs";
import type { FormBlockDef, FormCellDef, FormDef } from "./blankFormDefs";

export interface BlankForm {
  id: string;
  name: string;
  pages: number;
  /** 문서함에서 놓이는 폴더(11/17 디자인): 서식은 '기관 서식', 참고자료는 '참고 자료'. */
  folder: BlankFormFolderId;
}

export type BlankFormFolderId = "forms" | "ref";

/** 빈 양식이 놓이는 폴더 두 개(11/17 디자인 문서함). 화면에 들어 있는 폴더로, 서버 폴더가 아니다. */
export const BLANK_FORM_FOLDERS: { id: BlankFormFolderId; name: string }[] = [
  { id: "forms", name: "기관 서식" },
  { id: "ref", name: "참고 자료" },
];

/** 디자인 양식의 판 날짜. 문서함 날짜 정렬에도 쓴다. */
export const BLANK_FORM_DATE = "2026-11-09";

export const BLANK_FORMS: BlankForm[] = (
  [
    ["f4", "〈서식 4〉 초기면접지(아동용)", "forms"],
    ["f6", "〈서식 6〉 사정기록지", "forms"],
    ["f27", "〈서식 27〉 사례관리 점검표", "forms"],
    ["f29", "〈서식 29〉 사례관리 종결보고서", "forms"],
    ["r1", "〈참고자료 1〉 축약형 가족관계 척도", "ref"],
    ["r3", "〈참고자료 3〉 아동학대 위험수준별 개입 사정 척도", "ref"],
  ] as const
).map(([id, name, folder]) => ({ id, name, pages: BLANK_FORM_DEFS[id].pages, folder }));

export function blankFormById(id: string): BlankForm | null {
  return BLANK_FORMS.find((f) => f.id === id) ?? null;
}

export type PaperSeg =
  | { t: "s" | "g"; text: string }
  | { t: "br" }
  | { t: "sp"; q: string }
  | { t: "i"; key: string; aria: string; fill: boolean; width: string }
  | { t: "n"; key: string; aria: string }
  | { t: "ta"; key: string; aria: string; rows: number }
  | { t: "c"; key: string; aria: string; text: string; group: boolean; cls: string };

export interface PaperCell {
  cls: string;
  colSpan: number;
  rowSpan: number;
  segs: PaperSeg[];
}

export interface PaperBlock {
  cols: string;
  cells: PaperCell[];
}

export type PaperPage = PaperBlock[];

/** 입력값. 체크 묶음은 고른 글자, 묶음 없는 체크는 참 · 거짓, 나머지는 글자. */
export type BlankFormValues = Record<string, string | boolean>;

function paperBlock(def: FormDef, block: FormBlockDef): PaperBlock {
  // 입력칸의 읽기 이름은 바로 앞에 나온 글자를 쓴다(디자인과 같다). '(' 같은 기호만 있는 조각은 이름으로 쓰지 않는다.
  let label = "";
  const cell = (c: FormCellDef): PaperCell => ({
    cls: `fcell${c.k ? ` ${c.k}` : ""}${c.a === "c" ? " c" : ""}`,
    colSpan: c.c ?? 1,
    rowSpan: c.r ?? 1,
    segs: c.s.map((g): PaperSeg => {
      const last = String(g[g.length - 1]);
      const aria = label || def.title;
      switch (g[0]) {
        case "s":
          if (/[가-힣A-Za-z0-9]/.test(String(g[1]))) label = String(g[1]);
          return { t: "s", text: String(g[1]) };
        case "g":
          return { t: "g", text: String(g[1]) };
        case "br":
          return { t: "br" };
        case "sp":
          return { t: "sp", q: `q${g[1]}` };
        case "i":
          return { t: "i", key: last, aria, fill: g[1] === "f", width: String(g[1]) };
        case "n":
          return { t: "n", key: last, aria };
        case "t":
          return { t: "ta", key: last, aria, rows: Number(g[1]) };
        default:
          return {
            t: "c",
            key: g[2] ? String(g[2]) : last,
            group: !!g[2],
            text: String(g[1]),
            aria: (label && g[3] ? `${label} · ` : "") + String(g[1]),
            cls: `fcl${g[3] ? " only" : ""}${g[4] ? ` q${g[4]}` : ""}`,
          };
      }
    }),
  });
  return { cols: block.cols, cells: block.cells.map(cell) };
}

const paperCache = new Map<string, PaperPage[]>();

/** 양식을 쪽별로 그릴 값으로 바꾼다. 양식은 바뀌지 않으므로 한 번만 만든다. */
export function blankFormPages(id: string): PaperPage[] {
  const cached = paperCache.get(id);
  if (cached) return cached;
  const def = BLANK_FORM_DEFS[id];
  const pages: PaperPage[] = [];
  def.blocks.forEach((block) => {
    const p = block.p ?? 1;
    while (pages.length < p) pages.push([]);
    pages[p - 1].push(paperBlock(def, block));
  });
  paperCache.set(id, pages);
  return pages;
}

/** 1~10 숫자칸. 숫자가 아닌 글자를 빼고 범위 안으로 맞춘다(디자인과 같다). */
export function clampScore(raw: string): string {
  const digits = raw.replace(/[^0-9]/g, "");
  return digits === "" ? "" : String(Math.min(10, Math.max(1, parseInt(digits, 10))));
}

function escapeHtml(x: string): string {
  return x.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

const HTML_STYLE =
  "body{font-family:sans-serif;font-size:13px;color:#2B2A26;margin:24px}.page{max-width:860px;margin:0 auto 32px;page-break-after:always}" +
  ".g{display:grid;border-left:1px solid #8E897F;border-top:1px solid #8E897F;margin-top:-1px}" +
  ".c{display:flex;flex-wrap:wrap;align-items:center;gap:4px 10px;padding:6px 8px;min-height:30px;border-right:1px solid #8E897F;border-bottom:1px solid #8E897F}" +
  ".h{background:#D6D3CC;justify-content:center;text-align:center}.sec{background:#C9C5BC;justify-content:center;font-weight:600}" +
  ".title{justify-content:center;font-size:22px;font-weight:700;padding:16px}.ct{justify-content:center}.br{flex-basis:100%;height:0}" +
  ".v{min-width:40px;border-bottom:1px solid #8E897F;padding:0 4px}.tv{flex-basis:100%;white-space:pre-wrap;min-height:40px}" +
  ".gd{flex-basis:100%;white-space:pre-wrap;font-size:12px;font-style:italic;color:#6E6A62}.q4{flex:0 0 calc(25% - 8px)}.q3{flex:0 0 calc(33% - 7px)}";

/** 문서함에 저장하는 작성 양식 파일 확장자(서버 docbox_service FORM_EXT). */
export const FORM_FILE_EXT = "ispotform";

/** 칸 값(칸 이름 → 글 또는 체크). */
export type FormValues = Record<string, string | boolean>;

/**
 * 양식마다 아이 · 가족을 알아볼 수 있는 칸(이름 · 생년월일 · 나이 · 사건번호 · 가족 성명). 문서함은 모든 상담원이 보므로
 * 작성 창에서 못 쓰게 하고 파일에서도 뺀다. 서버(docbox_service FORM_IDENTITY_FIELDS)도 이 칸이 들어오면 422(민규 리뷰).
 */
const range = (from: number, to: number) => Array.from({ length: to - from + 1 }, (_, i) => `k${from + i}`);
export const IDENTITY_FIELDS: Record<string, ReadonlySet<string>> = {
  f4: new Set(["k14", "k15", ...range(16, 25), "k32", "k60", "k67", "k74", "k81"]),
  f6: new Set(["k10", "k11", "k12", "k13", "k14", "k15", "k16", "k17", "k24", "k27", "k30", "k33"]),
  f27: new Set(["k1", "k3"]),
  f29: new Set(["k1", "k4"]),
  r1: new Set(),
  r3: new Set(),
};

/** 작성 양식 파일 내용(JSON). 빈 칸 · 끈 체크 · 신원 칸은 넣지 않는다. 서버가 같은 꼴만 받는다. */
export function formFileText(formId: string, values: FormValues): string {
  const kept: FormValues = {};
  const locked = IDENTITY_FIELDS[formId] ?? new Set<string>();
  for (const [key, value] of Object.entries(values)) {
    if (locked.has(key)) continue;
    if (value === true || (typeof value === "string" && value.trim())) kept[key] = value;
  }
  return JSON.stringify({ kind: "ispot-blank-form", form_id: formId, version: BLANK_FORM_DATE, values: kept });
}

/** 작성 양식 파일을 읽는다. 꼴이 맞지 않거나 모르는 양식이면 null. */
export function parseFormFile(text: string): { formId: string; values: FormValues } | null {
  try {
    const doc = JSON.parse(text);
    if (!doc || doc.kind !== "ispot-blank-form" || !blankFormById(doc.form_id) || typeof doc.values !== "object" || !doc.values) {
      return null;
    }
    const values: FormValues = {};
    for (const [key, value] of Object.entries(doc.values as Record<string, unknown>)) {
      if (typeof value === "string" || value === true) values[key] = value;
    }
    return { formId: doc.form_id, values };
  } catch {
    return null;
  }
}

/** 저장 파일 이름에서 확장자를 뺀 제목. */
export function formFileTitle(name: string): string {
  return name.replace(new RegExp(`\\.${FORM_FILE_EXT}$`, "i"), "");
}

/**
 * 내려받을 HTML 을 만든다. values 를 주면 칸에 적고 고른 항목은 ☑(작성한 양식 내려받기, 11/09 디자인), 없으면 빈 양식.
 * 브라우저에서 열어 그대로 인쇄할 수 있다.
 */
export function blankFormHtml(form: BlankForm, values: FormValues = {}): string {
  const text = (key: string) => {
    const value = values[key];
    return typeof value === "string" && value ? escapeHtml(value) : "";
  };
  const body = blankFormPages(form.id)
    .map((page) => {
      const blocks = page
        .map((block) => {
          const cells = block.cells
            .map((c) => {
              const cls = `c${c.cls.replace("fcell", "").replace(/ c$/, " ct")}`;
              const segs = c.segs
                .map((g) => {
                  switch (g.t) {
                    case "s":
                      return `<span>${escapeHtml(g.text)}</span>`;
                    case "g":
                      return `<span class="gd">${escapeHtml(g.text)}</span>`;
                    case "br":
                      return '<span class="br"></span>';
                    case "sp":
                      return `<span class="${g.q}"></span>`;
                    case "i":
                    case "n":
                      return `<span class="v">${text(g.key) || "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"}</span>`;
                    case "ta":
                      return `<div class="tv">${text(g.key)}</div>`;
                    default: {
                      const q = /q\d/.exec(g.cls)?.[0];
                      const label = g.cls.includes("only") ? "" : ` ${escapeHtml(g.text)}`;
                      const on = g.group ? values[g.key] === g.text : !!values[g.key];
                      return `<span${q ? ` class="${q}"` : ""}>${on ? "☑" : "☐"}${label}</span>`;
                    }
                  }
                })
                .join("");
              return `<div class="${cls}" style="grid-column:span ${c.colSpan};grid-row:span ${c.rowSpan}">${segs}</div>`;
            })
            .join("");
          return `<div class="g" style="grid-template-columns:${block.cols}">${cells}</div>`;
        })
        .join("");
      return `<div class="page">${blocks}</div>`;
    })
    .join("");
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>${escapeHtml(form.name)}</title><style>${HTML_STYLE}</style></head><body>${body}</body></html>`;
}

/** 양식을 HTML 파일로 내려받는다(values 가 있으면 적은 내용과 함께). 서버를 부르지 않는다. */
export function downloadBlankForm(form: BlankForm, values: FormValues = {}, title?: string): boolean {
  try {
    const url = URL.createObjectURL(new Blob([blankFormHtml(form, values)], { type: "text/html;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${title || form.name}.html`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
    return true;
  } catch {
    return false;
  }
}
