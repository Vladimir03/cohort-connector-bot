import { Card, CardSub, CardTitle, CardValue } from "../components/ui";
import { useFunnel, useStats, useTimeline } from "../lib/api";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  BarChart, Bar, FunnelChart, Funnel, LabelList, Cell,
} from "recharts";

const SEG_COLORS: Record<string, string> = {
  pre_webinar: "#71717a", attended_live: "#3b82f6", no_show: "#f97316",
  hot_lead: "#10b981", customer: "#8b5cf6", churned: "#ef4444",
};

export default function Dashboard() {
  const stats = useStats();
  const funnel = useFunnel();
  const tl = useTimeline("hour", 7);

  const s = stats.data;
  const customers = s?.by_segment?.customer ?? 0;
  const hotLeads = s?.by_segment?.hot_lead ?? 0;
  const total = s?.users_total ?? 0;
  const conv = total ? ((hotLeads / total) * 100).toFixed(1) : "0";
  const revenue = customers * 65000;

  const segData = s
    ? Object.entries(s.by_segment).map(([name, count]) => ({ name, count, fill: SEG_COLORS[name] ?? "#71717a" }))
    : [];
  const funnelData = funnel.data?.stages.map((s, i) => ({
    name: s.name, value: s.count, fill: ["#10b981", "#3b82f6", "#8b5cf6", "#f59e0b", "#ef4444"][i],
  })) ?? [];

  const tlData = (tl.data ?? []).map((p) => ({ ...p, label: p.bucket.slice(5, 13).replace("T", " ") }));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardTitle>Total Users</CardTitle>
          <CardValue>{total}</CardValue>
          <CardSub>Active: {s?.users_active ?? 0} · Unsub: {s?.users_unsubscribed ?? 0}</CardSub>
        </Card>
        <Card>
          <CardTitle>Registered last 24h</CardTitle>
          <CardValue>{s?.registered_last_24h ?? 0}</CardValue>
          <CardSub>1h: {s?.registered_last_1h ?? 0} · 7d: {s?.registered_last_7d ?? 0}</CardSub>
        </Card>
        <Card>
          <CardTitle>Hot Leads</CardTitle>
          <CardValue>{hotLeads}</CardValue>
          <CardSub>{conv}% of total</CardSub>
        </Card>
        <Card>
          <CardTitle>Customers</CardTitle>
          <CardValue>{customers}</CardValue>
          <CardSub className="text-emerald-400">≈ {revenue.toLocaleString("ru-RU")} ₽</CardSub>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardTitle>Registrations / events · last 7 days</CardTitle>
          <div className="h-72 mt-3">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={tlData}>
                <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
                <XAxis dataKey="label" stroke="#71717a" tick={{ fontSize: 11 }} />
                <YAxis stroke="#71717a" tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }} />
                <Line type="monotone" dataKey="registrations" stroke="#10b981" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="events" stroke="#8b5cf6" strokeWidth={1.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <CardTitle>Segments</CardTitle>
          <div className="h-72 mt-3">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={segData} layout="vertical" margin={{ left: 30 }}>
                <CartesianGrid stroke="#27272a" strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" stroke="#71717a" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="name" stroke="#71717a" tick={{ fontSize: 11 }} width={100} />
                <Tooltip contentStyle={{ backgroundColor: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }} />
                <Bar dataKey="count">
                  {segData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <Card>
        <CardTitle>Conversion funnel</CardTitle>
        <div className="mt-4 space-y-3">
          {funnel.data?.stages.map((stage, i) => {
            const prev = i === 0 ? null : funnel.data!.stages[0].count;
            const widthPct = prev ? Math.max(2, (stage.count / prev) * 100) : 100;
            return (
              <div key={stage.name} className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="text-zinc-300">{stage.name}</span>
                  <span className="tabular-nums text-zinc-100">
                    {stage.count}
                    {stage.rate_from_prev !== null && (
                      <span className="ml-2 text-xs text-zinc-500">
                        {(stage.rate_from_prev * 100).toFixed(1)}% from prev
                      </span>
                    )}
                  </span>
                </div>
                <div className="h-3 rounded bg-zinc-800 overflow-hidden">
                  <div
                    className="h-full rounded"
                    style={{
                      width: `${widthPct}%`,
                      background: ["#10b981", "#3b82f6", "#8b5cf6", "#f59e0b", "#ef4444"][i] ?? "#10b981",
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
