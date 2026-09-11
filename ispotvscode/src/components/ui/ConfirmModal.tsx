import { useEffect } from "react";

interface Props {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmModal({ open, title, message, confirmLabel = "확인", onConfirm, onCancel }: Props) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(0,0,0,0.35)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}
    >
      <div className="bg-white rounded-[8px] shadow-sm border border-[#E2E8F0] w-full mx-4" style={{ maxWidth: "420px" }}>
        <div className="px-6 py-5 border-b border-[#E2E8F0]">
          <h3 className="text-[15px] font-semibold text-[#172033]">{title}</h3>
        </div>
        <div className="px-6 py-4">
          <p className="text-[13px] text-[#64748B] leading-relaxed">{message}</p>
        </div>
        <div className="px-6 py-4 border-t border-[#E2E8F0] flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-[13px] font-medium text-[#64748B] border border-[#E2E8F0] rounded-[6px] hover:bg-[#F8FAFC] transition-colors"
          >
            취소
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 text-[13px] font-semibold text-white bg-[#2563EB] hover:bg-[#1D4ED8] rounded-[6px] transition-colors"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
