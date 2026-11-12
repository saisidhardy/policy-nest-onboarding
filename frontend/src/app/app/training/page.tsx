"use client";

import { useEffect, useState } from "react";
import { Alert, Badge, Button, Card, CardHeader, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { TrainingModule } from "@/lib/types";

interface Question { id:string; category:string; prompt:string; options:string[] }
interface Attempt { id:string; attempt_number:number; questions:Question[] }

export default function TrainingPage() {
  const [modules,setModules]=useState<TrainingModule[]|null>(null); const [attempt,setAttempt]=useState<Attempt|null>(null); const [answers,setAnswers]=useState<Record<string,number>>({}); const [message,setMessage]=useState<string|null>(null); const [locked,setLocked]=useState(false);
  async function load(){try{setModules(await api<TrainingModule[]>("/training/modules"));}catch(e){if(e instanceof ApiError&&e.code==="TRAINING_LOCKED")setLocked(true);else setMessage(e instanceof Error?e.message:"Unable to load training.");}}
  useEffect(()=>{void load();},[]);
  async function complete(code:string,minutes:number){await api(`/training/modules/${code}`,{method:"PUT",body:{minutes_completed:minutes}});await load();}
  async function start(){try{setAttempt(await api<Attempt>("/training/exam/start",{method:"POST"}));}catch(e){setMessage(e instanceof Error?e.message:"Exam unavailable.");}}
  async function submit(){if(!attempt)return;try{const result=await api<{score_percent:number;passed:boolean;certificate_number:string|null}>(`/training/exam/${attempt.id}/submit`,{method:"POST",body:{answers}});setMessage(`${result.passed?"Passed":"Not passed"} — score ${result.score_percent}%${result.certificate_number?`. Certificate ${result.certificate_number}`:""}`);setAttempt(null);}catch(e){setMessage(e instanceof Error?e.message:"Submission failed.");}}
  if(locked)return <><PageHeader title="Training & exam"/><Alert tone="warning">Training opens after your KYC review is approved.</Alert></>;
  if(!modules)return <Spinner/>;
  const allComplete=modules.every((m)=>m.completed);
  return <div className="space-y-6"><PageHeader title="15-hour training & assessment" description="Complete all four recorded modules, then pass the 50-question assessment with at least 70%. Up to three attempts are allowed, with a 24-hour cooldown after an unsuccessful attempt." />{message&&<Alert>{message}</Alert>}
    <div className="grid gap-4 sm:grid-cols-2">{modules.map((m)=><Card key={m.code}><CardHeader title={m.title} action={<Badge tone={m.completed?"success":"warning"}>{m.minutes_completed}/{m.required_minutes} min</Badge>}/><div className="p-5"><div className="h-2 rounded bg-slate-100"><div className="h-2 rounded bg-brand-600" style={{width:`${m.minutes_completed/m.required_minutes*100}%`}}/></div>{!m.completed&&<Button className="mt-4" size="sm" onClick={()=>complete(m.code,m.required_minutes)}>Record module complete</Button>}</div></Card>)}</div>
    {!attempt&&<Button disabled={!allComplete} onClick={start}>Start 50-question exam</Button>}
    {attempt&&<Card><CardHeader title={`Exam attempt ${attempt.attempt_number}`} description={`${Object.keys(answers).length}/50 answered`}/><div className="divide-y divide-slate-100">{attempt.questions.map((q,index)=><fieldset key={q.id} className="p-5"><legend className="font-medium">{index+1}. {q.prompt}</legend><div className="mt-3 grid gap-2">{q.options.map((option,i)=><label key={option} className="flex gap-2 text-sm"><input type="radio" name={q.id} checked={answers[q.id]===i} onChange={()=>setAnswers({...answers,[q.id]:i})}/>{option}</label>)}</div></fieldset>)}</div><div className="p-5"><Button disabled={Object.keys(answers).length!==50} onClick={submit}>Submit assessment</Button></div></Card>}
    {!attempt&&<div className="flex flex-wrap gap-4 text-sm font-medium text-brand-700"><a className="hover:underline" href="/api/v1/training/certificate.pdf">Download certificate, if issued</a><a className="hover:underline" href="/verify-certificate">Verify a certificate</a></div>}
  </div>;
}
