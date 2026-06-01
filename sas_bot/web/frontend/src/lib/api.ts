import { useQuery, useMutation } from "@tanstack/react-query";

async function http<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { credentials: "include", ...init });
  if (!res.ok) throw new Error(`${res.status} ${await res.text().catch(() => "")}`);
  return res.json();
}

export type Segment = "pre_webinar" | "attended_live" | "no_show" | "hot_lead" | "customer" | "churned";
export const ALL_SEGMENTS: Segment[] = ["pre_webinar", "attended_live", "no_show", "hot_lead", "customer", "churned"];

export interface Stats {
  users_total: number; users_active: number; users_unsubscribed: number;
  by_segment: Record<string, number>;
  registered_last_1h: number; registered_last_24h: number; registered_last_7d: number;
  events_last_24h: number;
}
export interface FunnelStage { name: string; count: number; rate_from_prev: number | null }
export interface TimelinePoint { bucket: string; registrations: number; events: number }
export interface User {
  tg_id: number; username: string | null; name: string; role: string | null;
  segment: Segment; unsubscribed: boolean; registered_at: string;
  events_count: number | null; last_event_at: string | null;
}
export interface UserEvent { id: number; event_type: string; created_at: string; meta: string | null }
export interface EventRow { id: number; user_id: number; username: string | null; name: string | null; event_type: string; created_at: string; meta: string | null }

export const useStats = () => useQuery({ queryKey: ["stats"], queryFn: () => http<Stats>("/api/stats"), refetchInterval: 30_000 });
export const useFunnel = () => useQuery({ queryKey: ["funnel"], queryFn: () => http<{ stages: FunnelStage[] }>("/api/funnel"), refetchInterval: 30_000 });
export const useTimeline = (bucket: "hour" | "day", days: 1 | 7 | 30) =>
  useQuery({ queryKey: ["timeline", bucket, days], queryFn: () => http<TimelinePoint[]>(`/api/timeline?bucket=${bucket}&days=${days}`), refetchInterval: 30_000 });

export const useUsers = (segment: string, search: string, limit: number, offset: number) =>
  useQuery({
    queryKey: ["users", segment, search, limit, offset],
    queryFn: () => http<{ items: User[]; total: number }>(
      `/api/users?${new URLSearchParams({ ...(segment ? { segment } : {}), ...(search ? { search } : {}), limit: String(limit), offset: String(offset) })}`,
    ),
  });

export const useUserDetail = (tg_id: number | null) =>
  useQuery({
    queryKey: ["user", tg_id],
    queryFn: () => http<{ user: User; events: UserEvent[] }>(`/api/users/${tg_id}`),
    enabled: tg_id !== null,
  });

export const useEvents = (event_type: string, user_id: string, limit: number, offset: number) =>
  useQuery({
    queryKey: ["events", event_type, user_id, limit, offset],
    queryFn: () => http<{ items: EventRow[]; total: number; types: string[] }>(
      `/api/events?${new URLSearchParams({ ...(event_type ? { event_type } : {}), ...(user_id ? { user_id } : {}), limit: String(limit), offset: String(offset) })}`,
    ),
  });

export const useSetSegment = () =>
  useMutation({
    mutationFn: ({ tg_id, segment }: { tg_id: number; segment: Segment }) =>
      http(`/api/users/${tg_id}/segment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ segment }),
      }),
  });

export const useUnsubscribeUser = () =>
  useMutation({
    mutationFn: (tg_id: number) =>
      http(`/api/users/${tg_id}/unsubscribe`, { method: "POST" }),
  });

export const useBroadcast = () =>
  useMutation({
    mutationFn: (body: { segment: string; text: string; preview: boolean }) =>
      http<{ preview?: boolean; would_send_to?: number; sent?: number; failed?: number; total_targets?: number }>(
        "/api/broadcast",
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
      ),
  });
