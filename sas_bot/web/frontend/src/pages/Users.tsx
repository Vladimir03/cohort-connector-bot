import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  ALL_SEGMENTS, Segment, useUsers, useUserDetail, useSetSegment, useUnsubscribeUser,
} from "../lib/api";
import {
  Badge, Button, Card, Dialog, Input, Select, Table, Td, Th, Thead, Tr, relativeTime,
} from "../components/ui";

export default function UsersPage() {
  const [segment, setSegment] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [openId, setOpenId] = useState<number | null>(null);

  useEffect(() => {
    const t = setTimeout(() => { setSearch(searchInput); setOffset(0); }, 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  const q = useUsers(segment, search, limit, offset);
  const items = q.data?.items ?? [];
  const total = q.data?.total ?? 0;

  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center gap-3">
        <Select value={segment} onChange={(e) => { setSegment(e.target.value); setOffset(0); }}>
          <option value="">All segments</option>
          {ALL_SEGMENTS.map((s) => <option key={s} value={s}>{s}</option>)}
        </Select>
        <Input
          placeholder="Search username or name…"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className="max-w-xs"
        />
        <Select value={limit} onChange={(e) => { setLimit(Number(e.target.value)); setOffset(0); }}>
          <option value={25}>25</option><option value={50}>50</option><option value={100}>100</option>
        </Select>
        <div className="ml-auto text-sm text-zinc-400 tabular-nums">{total} total</div>
      </Card>

      <Card className="p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <Table>
            <Thead>
              <tr>
                <Th>Username</Th><Th>Name</Th><Th>Role</Th><Th>Segment</Th>
                <Th>Registered</Th><Th>Events</Th><Th></Th>
              </tr>
            </Thead>
            <tbody>
              {items.map((u) => (
                <Tr key={u.tg_id}>
                  <Td>
                    {u.username ? (
                      <a href={`tg://user?id=${u.tg_id}`} className="text-emerald-400 hover:underline mono">@{u.username}</a>
                    ) : <span className="text-zinc-600 mono">—</span>}
                  </Td>
                  <Td>{u.name}</Td>
                  <Td className="text-zinc-400">{u.role ?? "—"}</Td>
                  <Td><Badge tone={u.segment}>{u.segment}</Badge></Td>
                  <Td className="text-zinc-400 text-xs">{relativeTime(u.registered_at)}</Td>
                  <Td className="tabular-nums text-zinc-400">{u.events_count ?? 0}</Td>
                  <Td><Button variant="ghost" onClick={() => setOpenId(u.tg_id)}>Open</Button></Td>
                </Tr>
              ))}
              {items.length === 0 && !q.isLoading && (
                <tr><td colSpan={7} className="text-center text-zinc-500 py-10">No users</td></tr>
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

      <UserDialog tg_id={openId} onClose={() => setOpenId(null)} />
    </div>
  );
}

function UserDialog({ tg_id, onClose }: { tg_id: number | null; onClose: () => void }) {
  const qc = useQueryClient();
  const q = useUserDetail(tg_id);
  const setSeg = useSetSegment();
  const unsub = useUnsubscribeUser();
  const [newSeg, setNewSeg] = useState<Segment | "">("");

  useEffect(() => { if (q.data) setNewSeg(q.data.user.segment); }, [q.data]);

  if (!tg_id) return null;
  const d = q.data;

  const applySeg = async () => {
    if (!newSeg) return;
    await setSeg.mutateAsync({ tg_id, segment: newSeg as Segment });
    qc.invalidateQueries({ queryKey: ["users"] });
    qc.invalidateQueries({ queryKey: ["user", tg_id] });
    qc.invalidateQueries({ queryKey: ["stats"] });
  };
  const applyUnsub = async () => {
    await unsub.mutateAsync(tg_id);
    qc.invalidateQueries({ queryKey: ["users"] });
    qc.invalidateQueries({ queryKey: ["user", tg_id] });
    qc.invalidateQueries({ queryKey: ["stats"] });
  };

  return (
    <Dialog open={tg_id !== null} onClose={onClose}>
      {!d ? <div className="text-zinc-400">Loading…</div> : (
        <div className="space-y-4">
          <div>
            <div className="text-xl font-semibold">{d.user.name}</div>
            <div className="text-sm text-zinc-400 mono">
              {d.user.username ? `@${d.user.username} · ` : ""}tg_id={d.user.tg_id}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div><span className="text-zinc-500">Role:</span> {d.user.role ?? "—"}</div>
            <div><span className="text-zinc-500">Segment:</span> <Badge tone={d.user.segment}>{d.user.segment}</Badge></div>
            <div><span className="text-zinc-500">Registered:</span> {d.user.registered_at}</div>
            <div><span className="text-zinc-500">Unsubscribed:</span> {d.user.unsubscribed ? "yes" : "no"}</div>
          </div>
          <div className="flex items-end gap-2 flex-wrap">
            <div>
              <div className="text-xs text-zinc-500 mb-1">Change segment</div>
              <Select value={newSeg} onChange={(e) => setNewSeg(e.target.value as Segment)}>
                {ALL_SEGMENTS.map((s) => <option key={s} value={s}>{s}</option>)}
              </Select>
            </div>
            <Button onClick={applySeg} disabled={setSeg.isPending || newSeg === d.user.segment}>Apply</Button>
            <Button variant="danger" onClick={applyUnsub} disabled={unsub.isPending || d.user.unsubscribed}>
              Mark unsubscribed
            </Button>
            <Button variant="ghost" onClick={onClose} className="ml-auto">Close</Button>
          </div>
          <div>
            <div className="text-xs uppercase text-zinc-500 mb-2">Last 30 events</div>
            <div className="space-y-2 max-h-72 overflow-y-auto">
              {d.events.length === 0 && <div className="text-zinc-500 text-sm">No events.</div>}
              {d.events.map((e) => (
                <div key={e.id} className="flex items-start gap-3 text-sm border-l-2 border-zinc-800 pl-3">
                  <div className="text-zinc-500 text-xs w-32 shrink-0">{relativeTime(e.created_at)}</div>
                  <div className="flex-1">
                    <Badge>{e.event_type}</Badge>
                    {e.meta && <div className="text-xs text-zinc-500 mono mt-1 break-all">{e.meta}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </Dialog>
  );
}
