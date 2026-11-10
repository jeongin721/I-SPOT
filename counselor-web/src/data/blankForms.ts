// 문서함의 빈 양식(11/09 디자인 '문서함 작성 양식', 2026-11-09).
//
// 디자인의 작성 양식 6종을 화면에서만 보여 준다. 입력한 값은 창이 열려 있는 동안 화면 메모리에만 있고,
// 서버 · 브라우저 저장소 · 내려받은 파일 어디에도 넣지 않는다. 이 양식에는 아동 이름 · 생년월일 칸이 있는데
// 문서함은 모든 상담원에게 보이므로, 저장은 사례와 권한을 정한 뒤에 따로 다룬다.
// 사례에 남기는 작성은 지금처럼 사례 상세 › 문서함(API_CONTRACT 22절)에서 한다.

import { BLANK_FORM_DEFS } from "./blankFormDefs";
import type { FormBlockDef, FormCellDef, FormDef } from "./blankFormDefs";

export interface BlankForm {
  id: string;
  name: string;
  pages: number;
}

/** 디자인 양식의 판 날짜. 문서함 날짜 정렬에도 쓴다. */
export const BLANK_FORM_DATE = "2026-11-09";

export const BLANK_FORMS: BlankForm[] = (
  [
    ["f4", "〈서식 4〉 초기면접지(아동용)"],
    ["f6", "〈서식 6〉 사정기록지"],
    ["f27", "〈서식 27〉 사례관리 점검표"],
    ["f29", "〈서식 29〉 사례관리 종결보고서"],
    ["r1", "〈참고자료 1〉 축약형 가족관계 척도"],
    ["r3", "〈참고자료 3〉 아동학대 위험수준별 개입 사정 척도"],
  ] as const
).map(([id, name]) => ({ id, name, pages: BLANK_FORM_DEFS[id].pages }));

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

/**
 * 내려받을 HTML 을 만든다. 값을 받지 않으므로 항상 빈 양식이다(입력값이 파일로 나가지 않게 한다).
 * 브라우저에서 열어 그대로 인쇄할 수 있다.
 */
export function blankFormHtml(form: BlankForm): string {
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
                      return '<span class="v">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>';
                    case "ta":
                      return '<div class="tv"></div>';
                    default: {
                      const q = /q\d/.exec(g.cls)?.[0];
                      const text = g.cls.includes("only") ? "" : ` ${escapeHtml(g.text)}`;
                      return `<span${q ? ` class="${q}"` : ""}>☐${text}</span>`;
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

/** 빈 양식을 HTML 파일로 내려받는다. 서버를 부르지 않는다. */
export function downloadBlankForm(form: BlankForm): boolean {
  try {
    const url = URL.createObjectURL(new Blob([blankFormHtml(form)], { type: "text/html;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${form.name}.html`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
    return true;
  } catch {
    return false;
  }
}
