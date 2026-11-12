"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Badge, Button, Card, CardHeader, EmptyState, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import type { ApplicationRecord } from "@/lib/types";

export default function ReviewsPage() {
  const [items, setItems] = useState<ApplicationRecord[] | null>(null);
  const [selected, setSelected] = useState<ApplicationRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { try { const data = await api<ApplicationRecord[]>("/reviews/queue"); setItems(data); setSelected((current)=>current ? data.find((x)=>x.id===current.id) ?? null : null); } catch(e) { setError(e instanceof Error ? e.message : "Queue unavailable."); } }, []);
  useEffect(()=>{ void load(); }, [load]);
  async function act(action: string) {
    if (!selected) return;
    const justification = window.prompt(action === "REQUEST_CORRECTION" ? "Describe the correction required" : "Enter the decision justification");
    if (!justification || justification.length < 10) return;
    try {
      const body = { action, justification, issues: action === "REQUEST_CORRECTION" ? [{ code:"APPLICANT_CORRECTION", message:justification }] : [] };
      setSelected(await api<ApplicationRecord>(`/reviews/${selected.id}/actions`, { method:"POST", body })); await load();
    } catch(e) { setError(e instanceof Error ? e.message : "Action failed."); }
  }
  return <div className="space-y-6"><PageHeader title="Review queue" description="Applications are filtered by your region and clearance." />
    {error && <Alert tone="error">{error}</Alert>}{!items ? <Spinner /> : items.length === 0 ? <Card><EmptyState title="No applications in your queue" /></Card> : <div className="grid gap-6 lg:grid-cols-5">
      <Card className="lg:col-span-2"><CardHeader title={`${items.length} queued`} /><div className="divide-y divide-slate-100">{items.map((item)=><button key={item.id} onClick={()=>setSelected(item)} className="w-full p-4 text-left hover:bg-slate-50"><div className="flex justify-between gap-2"><span className="font-medium">{item.applicant_name}</span><Badge>{item.status.replaceAll("_"," ")}</Badge></div><p className="mt-1 text-xs text-slate-500">{item.reference} · {item.region}</p></button>)}</div></Card>
      <Card className="lg:col-span-3">{!selected ? <EmptyState title="Select an application" /> : <><CardHeader title={selected.applicant_name ?? selected.reference} description={`${selected.reference} · ${selected.applicant_email}`} /><div className="space-y-5 p-5 text-sm">
        <dl className="grid grid-cols-2 gap-3"><div><dt className="text-slate-500">PAN</dt><dd>{selected.pan_number}</dd></div><div><dt className="text-slate-500">Region</dt><dd>{selected.region}</dd></div><div><dt className="text-slate-500">Documents</dt><dd>{selected.documents.length}/6</dd></div><div><dt className="text-slate-500">Sensitivity</dt><dd>{selected.sensitivity}</dd></div></dl>
        <div className="flex flex-wrap gap-2"><Button size="sm" variant="secondary" onClick={()=>act("ASSIGN_TO_ME")}>Assign to me</Button><Button size="sm" variant="secondary" onClick={()=>act("REQUEST_CORRECTION")}>Request correction</Button><Button size="sm" onClick={()=>act("APPROVE_KYC")}>Approve KYC</Button><Button size="sm" variant="secondary" onClick={()=>act("ESCALATE")}>Escalate</Button><Button size="sm" variant="danger" onClick={()=>act("REJECT")}>Reject</Button></div>
      </div></>}</Card>
    </div>}
  </div>;
}
