// 사례의 실명 · 생년월일 · 가족 정보 훅(GET · PUT /cases/{id}/personal-info, API_CONTRACT 4절 '개인 식별 정보').
//
// 사례 상세의 탭(내담자 정보 · 상담 이력 · 문서함 · 초기면접지)이 머리의 실명과 인쇄 · 복사 가리기 이름 목록에 쓴다.
// 부를 때마다 서버에 열람 기록이 남는다. 값은 이 훅의 상태(useRemote)에만 있고 브라우저 저장소에 넣지 않는다.
// 로그아웃 · 다른 계정으로 바뀌는 중에는 key 가 null 이 되어 들고 있던 값을 버린다(useRemote).
// 저장된 값을 풀 수 없으면(500 PERSONAL_INFO_UNAVAILABLE) 오류 문구만 보이고 사례의 다른 기능은 그대로 쓴다.
//
// 값은 **지금 대상 세대에서 받은 것만** 내준다(info). useRemote 는 같은 key 로 돌아오면(A → B → A, B 를 받기 전) 앞에 받은
// A 값을 다시 보이는데, 그 값으로 통째로 바꾸는 PUT 을 하면 그사이 바뀐 최신 값을 지운다(Codex #129 R1). 그래서 받은 값에
// 그때의 세대를 붙여 두고, 세대가 다르면 null(불러오는 중과 같음)로 본다.
//
// 저장(save)은 통째로 바꾸는 PUT 이다. 값을 받기 전(불러오는 중 · 실패 · 앞 세대 값)에는 저장하지 않는다 — 모르는 값을 빈 칸으로
// 덮어 지우지 않게. 응답은 useCaseDetail.saveCase 처럼 보낼 때 잡은 표(capture)가 아직 지금 대상일 때만 반영하고,
// 대상 세대가 바뀌면 앞 대상 요청의 진행 표시 · 오류를 푼다(앞 사례의 늦은 저장이 새 사례 편집을 막지 않게 — #129 R4).

import { useCallback, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { cases } from "../api/endpoints";
import type { PersonalInfo, PersonalInfoRequest } from "../api/types";
import { errorMessage, useRemote, type RemoteTicket } from "./useRemote";

/** 받은 값과 그때의 대상 세대. */
interface Loaded {
  info: PersonalInfo;
  generation: number;
}

export interface PersonalInfoState {
  /** 지금 대상 세대에서 받은 값. 불러오는 중 · 실패 · 앞 세대 값이면 null. */
  info: PersonalInfo | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
  saving: boolean;
  saveError: string | null;
  /** 반영됐으면 true. 값을 받기 전이거나 이미 보내는 중이면 보내지 않고 false. */
  save: (payload: PersonalInfoRequest) => Promise<boolean>;
  capture: () => RemoteTicket | null;
  isCurrent: (ticket: RemoteTicket | null) => boolean;
}

export function usePersonalInfo(
  caseId: string | null | undefined,
  { enabled = true }: { enabled?: boolean } = {},
): PersonalInfoState {
  // 조회를 시작하는 때(useRemote 의 effect)의 대상 세대. 그리기마다 지금 세대로 맞춘다.
  const generationNow = useRef(0);
  const load = useCallback(
    (key: string): Promise<Loaded> => {
      const generation = generationNow.current;
      return cases.getPersonalInfo(key).then((info) => ({ info, generation }));
    },
    [],
  );
  const remote = useRemote<Loaded>(
    enabled && caseId ? caseId : null,
    load,
    "실명 · 가족 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
    () => false,
  );
  generationNow.current = remote.generation;

  const info = remote.data && remote.data.generation === remote.generation ? remote.data.info : null;
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [seenGeneration, setSeenGeneration] = useState(remote.generation);
  // 같은 순간의 두 번째 누름을 막는다(state 는 바로 바뀌지 않아 ref 로도 든다).
  const inFlight = useRef(false);
  const loaded = useRef(info);
  loaded.current = info;

  // 대상 세대가 바뀌면(다른 사례, 갔다 돌아옴, 다시 로그인) 앞 대상 요청의 진행 표시 · 오류를 푼다(그 응답은 반영하지 않는다).
  if (seenGeneration !== remote.generation) {
    setSeenGeneration(remote.generation);
    inFlight.current = false;
    setSaving(false);
    setSaveError(null);
  }

  const save = useCallback(
    async (payload: PersonalInfoRequest): Promise<boolean> => {
      const ticket = remote.capture();

      if (!ticket || !loaded.current || inFlight.current) return false;

      inFlight.current = true;
      setSaving(true);
      setSaveError(null);

      try {
        const saved = await cases.putPersonalInfo(ticket.key, payload);

        return remote.setData(ticket, { info: saved, generation: ticket.generation });
      } catch (caught) {
        // 대상이 바뀌었으면 오류 문구를 남기지 않는다(새 대상 화면에 앞 대상의 오류가 보이지 않게).
        if (remote.isCurrent(ticket) && !(caught instanceof ApiError && caught.isUnauthorized)) {
          setSaveError(errorMessage(caught, "실명 · 가족 정보를 저장하지 못했습니다. 잠시 후 다시 시도해 주세요."));
        }

        return false;
      } finally {
        // 대상 세대가 바뀌었으면 그때 이미 풀었다. 새 대상에서 보낸 요청의 표시를 끄지 않는다.
        if (remote.sameGeneration(ticket)) {
          inFlight.current = false;
          setSaving(false);
        }
      }
    },
    [remote.capture, remote.setData, remote.isCurrent, remote.sameGeneration],
  );

  return {
    info,
    loading: remote.loading || (remote.data !== null && info === null && remote.error === null),
    error: remote.error,
    reload: remote.reload,
    saving,
    saveError,
    save,
    capture: remote.capture,
    isCurrent: remote.isCurrent,
  };
}
