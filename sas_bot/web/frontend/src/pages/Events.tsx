import { useState } from "react";
import { useEvents } from "../lib/api";
import { Badge, Button, Card, Input, Select, Table, Td, Th, Thead, Tr, relativeTime } from "../components/ui";

export default function EventsPage() {
  const [eventType, setEventType] = useState("");
  const [userId, setUserId] = useState("");
  const [limit, setLimit] = useState(100);
  const [offset, setOffset] = useState(0);

  const q = useEvents(eventType, userId, limit, offset);
  const items = q.data?.items ?? [];
  const total = q.data?.total ?? 0;
  const types = q.data?.types ?? [];

  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center gap-3">
        <Select value={eventType} onChange={(e) => { setEventType(e.target.value); setOffset(0); }}>
          <option value="">All event types</option>
          {types.map((t) => <option key={t} value={t}>{t}</option>)}
        </Select>
        <Input
          placeholder="Filter by user_id…"
          value={userId}
          onChange={(e) => { setUserId(e.target.value.replace(/\D/g, "")); setOffset(0); }}
          className="max-w-xs mono"
        />
        <Select value={limit} onChange={(e) => { setLimit(Number(e.target.value)); setOffset(0); }}>
          <option value={50}>50</option><option value={100}>100</option><option value={200}>200</option>
        </Select>
        <div className="ml-auto text-sm text-zinc-400 tabular-nums">{total} total</div>
      </Card>

      <Card className="p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <Table>
            <Thead>
              <tr>
                <Th>Time</Th><Th>User</Th><Th>Event</Th><Th>Meta</Th>
              </tr>
            </Thead>
            <tbody>
              {items.map((e) => (
                <Tr key={e.id}>
                  <Td className="text-zinc-400 text-xs whitespace-nowrap">{relativeTime(e.created_at)}</Td>
                  <Td>
                    {e.username && <span className="text-emerald-400 mono">@{e.username}</span>}
                    {e.name && <span className="text-zinc-400 ml-2">{e.name}</span>}
                    {!e.username && !e.name && <span className="text-zinc-600 mono">{e.user_id}</span>}
                  </Td>
                  <Td><Badge>{e.event_type}</Badge></Td>
                  <Td className="text-xs text-zinc-500 mono max-w-md truncate">{e.meta ?? "—"}</Td>
                </Tr>
              ))}
              {items.length === 0 && !q.isLoading && (
                <tr><td colSpan={4} className="text-center text-zinc-500 py-10">No events</td></tr>
              )}
            </tbody>
          </Table>
        </div>
      </Card>

      <div className="flex justify-between items-center">
        <Button variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>← Previous</Button>
        <div className="text-sm text-zinc-500 tabular-nums">{offset + 1}–{Math.min(offset + limit, total)} of {total}</div>
        <Button variant="outline" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}>Next →</Button>
      </div>
    </div>
  );
}
