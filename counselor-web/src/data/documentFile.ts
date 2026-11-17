// 상담 기록 문서 파일 검사(녹취 · 자료 올리기 '문서 파일', 2026-11-02). 서버(app/services/document_text.py)와 같은 규칙이다.

export const DOCUMENT_EXTENSIONS = [".txt", ".docx", ".hwpx", ".pdf"];
export const DOCUMENT_MAX_BYTES = 10 * 1024 * 1024;
export const DOCUMENT_ACCEPT = DOCUMENT_EXTENSIONS.join(",");
export const DOCUMENT_RULE_TEXT = ".txt .docx .hwpx .pdf 문서, 10 MB까지 · 새 회차에만 · 상담일지(3단계)부터 채웁니다.";

/** 문서로 볼 파일인가(확장자). .hwp 도 문서로 보고 checkDocumentFile 이 안내한다. */
export function isDocumentFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return name.endsWith(".hwp") || DOCUMENT_EXTENSIONS.some((ext) => name.endsWith(ext));
}

/** 올릴 수 없으면 그 이유, 괜찮으면 null. */
export function checkDocumentFile(file: File): string | null {
  const name = file.name.toLowerCase();
  if (name.endsWith(".hwp")) return "HWP 파일은 읽지 못합니다. 한글에서 '다른 이름으로 저장' → HWPX 나 PDF 로 저장해 올려 주세요.";
  if (!DOCUMENT_EXTENSIONS.some((ext) => name.endsWith(ext))) return "문서는 .txt · .docx · .hwpx · .pdf 만 올릴 수 있습니다.";
  if (file.size === 0) return "빈 파일입니다.";
  if (file.size > DOCUMENT_MAX_BYTES) return "문서는 10 MB 까지 올릴 수 있습니다.";
  return null;
}
