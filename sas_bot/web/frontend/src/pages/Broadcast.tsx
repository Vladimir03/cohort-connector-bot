import { useState } from "react";
import { ALL_SEGMENTS, useBroadcast } from "../lib/api";
import { Button, Card, CardTitle, Dialog, Select, Textarea } from "../components/ui";

export default function BroadcastPage() {
  const [segment, setSegment] = useState("hot_lead");
  const [text, setText] = useState("");
  const [previewCount, setPreviewCount] = useState<number | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [result, setResult] = useState<{ sent?: number; failed?: number; total_targets?: number } | null>(null);
  const m = useBroadcast();

  const doPreview = async () => {
    setResult(null);
    const r = await m.mutateAsync({ segment, text: text || "preview", preview: true });
    setPreviewCount(r.would_send_to ?? 0);
  };
  const doSend = async () => {
    setConfirmOpen(false);
    const r = await m.mutateAsync({ segment, text, preview: false });
    setResult(r);
  };

  const segOptions = ["all", ...ALL_SEGMENTS];

  return (
    <div className="max-w-2xl space-y-4">
      <Card className="space-y-4">
        <CardTitle>New broadcast</CardTitle>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <div className="text-xs text-zinc-500 mb-1">Target segment</div>
            <Select value={segment} onChange={(e) => { setSegment(e.target.value); setPreviewCount(null); setResult(null); }}>
              {segOptions.map((s) => <option key={s} value={s}>{s === "all" ? "All active users" : s}</option>)}
            </Select>
          </div>
          <div className="flex items-end">
            <Button variant="outline" onClick={doPreview} disabled={m.isPending}>Preview count</Button>
            {previewCount !== null && (
              <span className="ml-3 text-sm text-zinc-300">
                Will be sent to <span className="text-emerald-400 font-semibold tabular-nums">{previewCount}</span> users
              </span>
            )}
          </div>
        </div>
        <div>
          <div className="flex justify-between text-xs text-zinc-500 mb-1">
            <span>Message text</span>
            <span className={text.length > 4000 ? "text-red-400" : ""}>{text.length}/4000</span>
          </div>
          <Textarea
            rows={10}
            value={text}
            maxLength={4000}
            onChange={(e) => { setText(e.target.value); setResult(null); }}
            placeholder="Привет, {name}! …  (используй {name} для подстановки имени)"
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button
            variant="default"
            disabled={text.trim().length === 0 || m.isPending}
            onClick={() => setConfirmOpen(true)}
          >
            Send broadcast
          </Button>
        </div>
        {result && (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm">
            ✅ Sent: <b>{result.sent}</b> · Failed: <b>{result.failed}</b> · Targets: <b>{result.total_targets}</b>
          </div>
        )}
      </Card>

      <Dialog open={confirmOpen} onClose={() => setConfirmOpen(false)}>
        <div className="space-y-4">
          <div className="text-lg font-semibold">Confirm broadcast</div>
          <p className="text-sm text-zinc-400">
            About to send to segment <b className="text-zinc-200">{segment}</b>
            {previewCount !== null && <> ({previewCount} users)</>}. This cannot be undone.
          </p>
          <div className="rounded bg-zinc-950 border border-zinc-800 p-3 text-sm whitespace-pre-wrap max-h-60 overflow-y-auto">
            {text}
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirmOpen(false)}>Cancel</Button>
            <Button variant="default" onClick={doSend} disabled={m.isPending}>
              {m.isPending ? "Sending…" : "Send now"}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
