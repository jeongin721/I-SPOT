// 사례 종결 확정(PATCH /cases/{id} status CLOSED, API_CONTRACT 4절, 2026-11-05).
//
// 종결보고서 저장(PUT closure-summary)과 따로 둔 마지막 단계다 — 상담원이 직접 눌러 확인해야 사례 상태가 바뀐다.
//  - 보고서를 한 번이라도 저장했고, 저장하지 않은 수정이 없을 때만 누를 수 있다(보고서와 종결 상태가 어긋나지 않게).
//  - 이미 종결한 사례는 '종결된 사례' 로 보이고 누를 수 없다. 되돌리기는 이 화면에서 하지 않는다.

import { useState } from "react";

import { ApiError } from "../api/client";
import { cases } from "../api/endpoints";
import type { ClosureReportFields } from "../api/types";
import type { CaseDetailState } from "./useCaseDetail";
import { errorMessage } from "./useRemote";

export function useCaseClosing(
  caseId: string | null,
  detail: CaseDetailState,
  savedReport: ClosureReportFields | null | undefined,
  unsaved: boolean,
) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const info = detail.caseInfo;
  const closed = info?.status === "CLOSED";
  const hasReport = Object.values(savedReport ?? {}).some((value) => value !== null && value !== undefined);

  let hint = "";
  if (closed) hint = done ? "사례를 종결했습니다." : "종결된 사례입니다.";
  else if (!hasReport) hint = "보고서를 저장한 뒤 종결 확정을 할 수 있습니다.";
  else if (unsaved) hint = "저장하지 않은 수정이 있습니다. 보고서를 저장한 뒤 종결 확정을 해 주세요.";

  return {
    label: closed ? "종결된 사례" : busy ? "종결 중…" : "사례 종결 확정",
    canClose: Boolean(caseId && info && !closed && hasReport && !unsaved && !busy),
    hint: error ?? hint,
    close: async () => {
      if (!caseId || !info || closed || busy) return;
      if (!window.confirm(`${info.alias} 사례를 종결합니다. 사례 상태가 '종결' 로 바뀝니다. 계속할까요?`)) return;
      setBusy(true);
      setError(null);
      try {
        await cases.update(caseId, { status: "CLOSED" });
        setDone(true);
        detail.refresh();
      } catch (caught) {
        if (!(caught instanceof ApiError && caught.isUnauthorized)) {
          setError(errorMessage(caught, "사례를 종결하지 못했습니다. 잠시 후 다시 시도해 주세요."));
        }
      } finally {
        setBusy(false);
      }
    },
  };
}
