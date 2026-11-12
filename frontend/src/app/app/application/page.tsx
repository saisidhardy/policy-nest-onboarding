"use client";

import { FormEvent, useEffect, useState } from "react";
import { Alert, Badge, Button, Card, CardHeader, Field, Input, PageHeader, Select, Spinner } from "@/components/ui";
import { api, ApiError, apiUpload } from "@/lib/api";
import type { ApplicationRecord, DocumentRecord } from "@/lib/types";

const DOCS = ["PAN", "AADHAAR", "EDUCATION_10TH", "PHOTO", "SIGNATURE", "BANK_PROOF"];
const REGIONS = ["NORTH", "SOUTH", "EAST", "WEST", "CENTRAL", "NORTHEAST"];

export default function ApplicationPage() {
  const [application, setApplication] = useState<ApplicationRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [form, setForm] = useState({ date_of_birth: "", pan_number: "", aadhaar_last4: "", region: "", address: "", city: "", pincode: "", qualification: "", account_holder: "", account_number: "", ifsc: "" });

  async function load() {
    try {
      const value = await api<ApplicationRecord>("/applications/mine");
      setApplication(value);
      setForm({
        date_of_birth: value.date_of_birth ?? "", pan_number: value.pan_number ?? "", aadhaar_last4: value.aadhaar_last4 ?? "",
        region: value.region ?? "", address: value.address.line1 ?? "", city: value.address.city ?? "", pincode: value.address.pincode ?? "",
        qualification: value.education.qualification ?? "", account_holder: value.bank_details.account_holder ?? "",
        account_number: value.bank_details.account_number ?? "", ifsc: value.bank_details.ifsc ?? "",
      });
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) setApplication(await api<ApplicationRecord>("/applications/mine", { method: "POST" }));
      else setMessage({ tone: "error", text: error instanceof Error ? error.message : "Unable to load application." });
    } finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  async function save(event: FormEvent) {
    event.preventDefault(); setSaving(true); setMessage(null);
    try {
      const value = await api<ApplicationRecord>("/applications/mine", { method: "PATCH", body: {
        current_step: 3, date_of_birth: form.date_of_birth, pan_number: form.pan_number, aadhaar_last4: form.aadhaar_last4, region: form.region,
        address: { line1: form.address, city: form.city, pincode: form.pincode }, education: { qualification: form.qualification },
        bank_details: { account_holder: form.account_holder, account_number: form.account_number, ifsc: form.ifsc.toUpperCase() },
        declarations: { information_true: true, data_processing_consent: true, exclusivity_confirmed: true },
      }});
      setApplication(value); setMessage({ tone: "success", text: "Draft saved." });
    } catch (error) { setMessage({ tone: "error", text: error instanceof Error ? error.message : "Save failed." }); }
    finally { setSaving(false); }
  }

  async function upload(type: string, file: File) {
    const data = new FormData(); data.set("document_type", type); data.set("file", file);
    try {
      const document = await apiUpload<DocumentRecord>("/applications/mine/documents", data);
      setApplication((current) => current ? { ...current, documents: [...current.documents.filter((d) => d.document_type !== type), document] } : current);
      setMessage({ tone: document.status === "UPLOADED" ? "success" : "error", text: document.status === "UPLOADED" ? `${type} uploaded.` : `${type} needs a clearer re-upload.` });
    } catch (error) { setMessage({ tone: "error", text: error instanceof Error ? error.message : "Upload failed." }); }
  }

  async function submit() {
    try { setApplication(await api<ApplicationRecord>("/applications/mine/submit", { method: "POST" })); setMessage({ tone: "success", text: "Application submitted for review." }); }
    catch (error) { setMessage({ tone: "error", text: error instanceof Error ? error.message : "Submission failed." }); }
  }

  if (loading) return <Spinner />;
  if (!application) return <Alert tone="error">Application could not be loaded.</Alert>;
  const editable = ["DRAFT", "CORRECTION_REQUIRED"].includes(application.status);
  const requiredFields = Object.values(form);
  const completedFields = requiredFields.filter((value) => value.trim().length > 0).length;
  const completedDocuments = DOCS.filter((type) => application.documents.some((document) => document.document_type === type && document.status === "UPLOADED")).length;
  const completion = Math.round(((completedFields + completedDocuments) / (requiredFields.length + DOCS.length)) * 100);
  return <div className="space-y-6">
    <PageHeader title="POSP onboarding application" description={`Reference ${application.reference}`} action={<Badge tone={editable ? "warning" : "brand"}>{application.status.replaceAll("_", " ")}</Badge>} />
    {message && <Alert tone={message.tone}>{message.text}</Alert>}
    <Card><CardHeader title="Application progress" description="Complete every section and upload all six required documents before submission." action={<Badge tone={completion === 100 ? "success" : "brand"}>{completion}%</Badge>} />
      <div className="p-5"><div className="h-2 overflow-hidden rounded bg-slate-100" role="progressbar" aria-label="Application completion" aria-valuemin={0} aria-valuemax={100} aria-valuenow={completion}><div className="h-full rounded bg-brand-600 transition-all" style={{width:`${completion}%`}} /></div>
        <ol className="mt-4 grid gap-2 text-sm sm:grid-cols-4">
          <li className={completedFields >= 4 ? "text-emerald-700" : "text-slate-500"}>1. Identity</li>
          <li className={completedFields >= 8 ? "text-emerald-700" : "text-slate-500"}>2. Address & education</li>
          <li className={completedFields === requiredFields.length ? "text-emerald-700" : "text-slate-500"}>3. Bank mandate</li>
          <li className={completedDocuments === DOCS.length ? "text-emerald-700" : "text-slate-500"}>4. Documents ({completedDocuments}/{DOCS.length})</li>
        </ol>
      </div>
    </Card>
    <form onSubmit={save} className="space-y-6">
      <Card><CardHeader title="Identity and eligibility" description="Enter the details exactly as they appear on your documents." />
        <div className="grid gap-4 p-5 sm:grid-cols-2">
          <Field label="Date of birth" htmlFor="dob"><Input id="dob" type="date" required disabled={!editable} value={form.date_of_birth} onChange={(e) => setForm({...form, date_of_birth:e.target.value})} /></Field>
          <Field label="PAN" htmlFor="pan"><Input id="pan" required maxLength={10} disabled={!editable} value={form.pan_number} onChange={(e) => setForm({...form, pan_number:e.target.value.toUpperCase()})} /></Field>
          <Field label="Aadhaar last 4 digits" htmlFor="aadhaar"><Input id="aadhaar" required pattern="[0-9]{4}" maxLength={4} disabled={!editable} value={form.aadhaar_last4} onChange={(e) => setForm({...form, aadhaar_last4:e.target.value})} /></Field>
          <Field label="Operating region" htmlFor="region"><Select id="region" required disabled={!editable} value={form.region} onChange={(e) => setForm({...form, region:e.target.value})}><option value="">Select</option>{REGIONS.map((r)=><option key={r}>{r}</option>)}</Select></Field>
          <Field label="Address" htmlFor="address"><Input id="address" required disabled={!editable} value={form.address} onChange={(e) => setForm({...form, address:e.target.value})} /></Field>
          <Field label="City" htmlFor="city"><Input id="city" required disabled={!editable} value={form.city} onChange={(e) => setForm({...form, city:e.target.value})} /></Field>
          <Field label="Pincode" htmlFor="pincode"><Input id="pincode" required pattern="[0-9]{6}" disabled={!editable} value={form.pincode} onChange={(e) => setForm({...form, pincode:e.target.value})} /></Field>
          <Field label="Highest qualification" htmlFor="qualification"><Input id="qualification" required disabled={!editable} value={form.qualification} onChange={(e) => setForm({...form, qualification:e.target.value})} /></Field>
        </div>
      </Card>
      <Card><CardHeader title="Bank mandate" /><div className="grid gap-4 p-5 sm:grid-cols-3">
        <Field label="Account holder" htmlFor="holder"><Input id="holder" required disabled={!editable} value={form.account_holder} onChange={(e)=>setForm({...form,account_holder:e.target.value})}/></Field>
        <Field label="Account number" htmlFor="account"><Input id="account" required disabled={!editable} value={form.account_number} onChange={(e)=>setForm({...form,account_number:e.target.value})}/></Field>
        <Field label="IFSC" htmlFor="ifsc"><Input id="ifsc" required disabled={!editable} value={form.ifsc} onChange={(e)=>setForm({...form,ifsc:e.target.value.toUpperCase()})}/></Field>
      </div></Card>
      {editable && <Button type="submit" loading={saving}>Save application</Button>}
    </form>
    <Card><CardHeader title="Required documents" description="PDF, JPEG, PNG or WebP; maximum 10 MB each." /><div className="grid gap-3 p-5 sm:grid-cols-2">
      {DOCS.map((type) => { const doc = application.documents.find((d)=>d.document_type===type); return <label key={type} className="rounded-lg border border-slate-200 p-4">
        <span className="flex items-center justify-between text-sm font-medium">{type.replaceAll("_"," ")} {doc && <Badge tone={doc.status === "UPLOADED" ? "success":"danger"}>{doc.status.replaceAll("_"," ")}</Badge>}</span>
        {editable && <input className="mt-3 block w-full text-sm" type="file" accept=".pdf,image/jpeg,image/png,image/webp" onChange={(e)=>e.target.files?.[0] && void upload(type,e.target.files[0])}/>} 
      </label>; })}
    </div></Card>
    {editable && <div className="flex items-center justify-end gap-3">{completion < 100 && <span className="text-sm text-slate-500">Complete all fields and documents to submit.</span>}<Button disabled={completion < 100} onClick={submit}>Submit for review</Button></div>}
  </div>;
}
