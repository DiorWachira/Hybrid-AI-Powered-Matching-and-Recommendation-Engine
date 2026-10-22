import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { api, type AuditCategory, type AuditEvent, type DailyActivity } from "../lib/api";
import { ListPagination } from "./ListPagination";
import { ActivityColumns, describeEvent, eventTone, relativeTime } from "./Insights";

const PAGE_SIZE = 12;
const categories: Array<[AuditCategory | "", string]> = [["", "Everything"], ["account", "Accounts"], ["application", "Applications"], ["job", "Postings"], ["matches", "Matching"], ["profile", "Profiles"], ["resume", "Resumes"], ["ontology", "Ontology"]];
const dayLabel = (value: string) => {
  const day = new Date(value); const today = new Date();
  const difference = Math.round((new Date(today.toDateString()).getTime() - new Date(day.toDateString()).getTime()) / 86_400_000);
  return difference === 0 ? "Today" : difference === 1 ? "Yesterday" : day.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
};

export function AdminActivityLog({ trend }: { trend: DailyActivity[] }) {
  const [category, setCategory] = useState<AuditCategory | "">("");
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(null);
    void api.auditLog(localStorage.getItem("jobbridge_token") ?? "", category, offset, PAGE_SIZE + 1)
      .then((data) => { if (active) setEvents(data); })
      .catch((reason: Error) => { if (active) { setError(reason.message); setEvents([]); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [category, offset, refresh]);

  const visible = events.slice(0, PAGE_SIZE);
  const groups: Array<[string, AuditEvent[]]> = [];
  for (const event of visible) {
    const label = dayLabel(event.created_at);
    if (groups.at(-1)?.[0] === label) groups.at(-1)![1].push(event); else groups.push([label, [event]]);
  }
  const weekTotal = trend.slice(-7).reduce((sum, day) => sum + day.events, 0);

  return <div className="admin-panel-body">
    {trend.length > 0 && <div className="activity-trend"><div><strong>{weekTotal}</strong><span>events in the last 7 days</span></div><ActivityColumns days={trend.map((day) => day.day)} values={trend.map((day) => day.events)} /><small>Last {trend.length} days</small></div>}
    <div className="admin-filter-bar">
      <div className="chip-group" role="group" aria-label="Filter activity">{categories.map(([value, label]) => <button key={value} type="button" className="chip" aria-pressed={category === value} onClick={() => { setCategory(value); setOffset(0); }}>{label}</button>)}</div>
      <button className="icon-button" title="Refresh activity" aria-label="Refresh activity" disabled={loading} onClick={() => setRefresh((value) => value + 1)}><RefreshCw size={16} /></button>
    </div>
    {error && <p className="notice error" role="alert">{error}</p>}
    <div className="activity-feed" aria-busy={loading}>
      {groups.map(([label, items]) => <section key={label}><h3>{label}</h3><ol>{items.map((event) => <li key={event.event_id} className={`tone-${eventTone(event.action)}`}>
        <i aria-hidden="true" />
        <p><strong title={event.actor_user_id ?? undefined}>{event.actor_email ?? (event.actor_user_id ? `User ${event.actor_user_id.slice(0, 8)}` : "System")}</strong> {describeEvent(event)}{event.resource_id && <span className="activity-resource" title={event.resource_id}> · {event.resource_type} {event.resource_id.slice(0, 8)}</span>}</p>
        <time dateTime={event.created_at} title={new Date(event.created_at).toLocaleString()}>{relativeTime(event.created_at)}</time>
      </li>)}</ol></section>)}
      {!visible.length && <p className="admin-applicant-empty" role="status">{loading ? "Loading activity..." : error ? "Activity unavailable" : "Nothing recorded in this category yet"}</p>}
    </div>
    <ListPagination label="activity" offset={offset} pageSize={PAGE_SIZE} hasNext={events.length > PAGE_SIZE} disabled={loading} onChange={setOffset} />
  </div>;
}
