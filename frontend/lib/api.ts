const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const API_V1 = `${API_BASE_URL}/api/v1`;

export type CaseItem = {
  id: string;
  title: string;
  description: string | null;
  created_at: string;
};

export type SessionItem = {
  id: string;
  case_id: string;
  title: string;
  status: string;
  created_at: string;
};

type Envelope<T> = { data: T };
type ErrorEnvelope = { error: { code: string; message: string } };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_V1}${path}`, {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    ...init,
  });
  const body = await res.json();
  if (!res.ok) {
    const err = (body as ErrorEnvelope).error;
    throw new Error(err?.message ?? `Request failed (${res.status})`);
  }
  return (body as Envelope<T>).data;
}

export const api = {
  listCases: () => request<CaseItem[]>("/cases"),
  createCase: (payload: { title: string; description?: string }) =>
    request<CaseItem>("/cases", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listSessions: (caseId: string) =>
    request<SessionItem[]>(`/cases/${caseId}/sessions`),
  createSession: (caseId: string, payload: { title: string }) =>
    request<SessionItem>(`/cases/${caseId}/sessions`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
