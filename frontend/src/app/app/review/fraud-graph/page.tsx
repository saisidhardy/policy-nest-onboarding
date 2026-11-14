"use client";

import clsx from "clsx";
import {
  AlertTriangle,
  ArrowRight,
  Building2,
  DownloadCloud,
  FileCheck2,
  Filter,
  Lock,
  PhoneCall,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  UserX,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { RequirePermission } from "@/components/RequirePermission";
import { ReviewPortalTabs } from "@/components/review/ReviewPortalTabs";
import { Alert, Badge, Button, Card, PageHeader } from "@/components/ui";

interface FraudNode {
  id: string;
  label: string;
  type: "applicant" | "bank" | "phone" | "doc_hash";
  riskScore: number;
  status: "CRITICAL" | "SUSPICIOUS" | "RESOLVED";
  x: number;
  y: number;
  details: {
    pan?: string;
    account?: string;
    bankName?: string;
    phone?: string;
    hash?: string;
    applicationRef?: string;
    triggeredRules: string[];
    linkedEntityIds: string[];
  };
}

interface FraudEdge {
  from: string;
  to: string;
  type: "mule_account" | "contact_stack" | "doc_duplicate";
  label: string;
}

const INITIAL_NODES: FraudNode[] = [
  // Ring 1: Mule Bank Collision (3 disparate PANs pointing to same bank account)
  {
    id: "bank-1",
    label: "HDFC Acc ...0042",
    type: "bank",
    riskScore: 96,
    status: "CRITICAL",
    x: 320,
    y: 180,
    details: {
      account: "50100492810042",
      bankName: "HDFC Bank (Connaught Place)",
      triggeredRules: ["FR-MULE-BANK-COLLISION", "RULE-4.5-ACCOUNT-NAME-MISMATCH"],
      linkedEntityIds: ["app-1", "app-2", "app-3"],
    },
  },
  {
    id: "app-1",
    label: "Rajiv Sharma",
    type: "applicant",
    riskScore: 92,
    status: "CRITICAL",
    x: 180,
    y: 100,
    details: {
      pan: "ABCPS1234F",
      applicationRef: "PN-2026-0891",
      triggeredRules: ["FR-MULE-BANK-COLLISION", "RULE-1.2-CROSS-APP-DUP"],
      linkedEntityIds: ["bank-1", "phone-1"],
    },
  },
  {
    id: "app-2",
    label: "Priya V. Verma",
    type: "applicant",
    riskScore: 89,
    status: "CRITICAL",
    x: 180,
    y: 260,
    details: {
      pan: "DFGPP9812K",
      applicationRef: "PN-2026-0904",
      triggeredRules: ["FR-MULE-BANK-COLLISION"],
      linkedEntityIds: ["bank-1"],
    },
  },
  {
    id: "app-3",
    label: "Amit K. Joshi",
    type: "applicant",
    riskScore: 94,
    status: "CRITICAL",
    x: 460,
    y: 130,
    details: {
      pan: "JKLPJ4512M",
      applicationRef: "PN-2026-0922",
      triggeredRules: ["FR-MULE-BANK-COLLISION", "FR-PHONE-STACKING"],
      linkedEntityIds: ["bank-1", "phone-1"],
    },
  },

  // Ring 2: Contact Stacking Ring (Same phone number used across 4 PANs)
  {
    id: "phone-1",
    label: "+91 98112 04812",
    type: "phone",
    riskScore: 88,
    status: "CRITICAL",
    x: 520,
    y: 280,
    details: {
      phone: "+91 98112 04812",
      triggeredRules: ["FR-PHONE-STACKING-EXCEEDED-THRESHOLD (Limit: 2)"],
      linkedEntityIds: ["app-1", "app-3", "app-4"],
    },
  },
  {
    id: "app-4",
    label: "Suresh Rao",
    type: "applicant",
    riskScore: 78,
    status: "SUSPICIOUS",
    x: 680,
    y: 260,
    details: {
      pan: "MNBPR6712L",
      applicationRef: "PN-2026-0975",
      triggeredRules: ["FR-PHONE-STACKING"],
      linkedEntityIds: ["phone-1"],
    },
  },

  // Ring 3: Document Hash Clone Attack (Exact same photo uploaded under two names)
  {
    id: "doc-1",
    label: "SHA256: 8f4c...b912",
    type: "doc_hash",
    riskScore: 99,
    status: "CRITICAL",
    x: 380,
    y: 380,
    details: {
      hash: "8f4c9a72e104b912ef6530182410a563",
      triggeredRules: ["FR-SHA256-IMAGE-COLLISION", "RULE-3.1-IMAGE-DUPLICATE"],
      linkedEntityIds: ["app-2", "app-5"],
    },
  },
  {
    id: "app-5",
    label: "Neha Patel (Alias)",
    type: "applicant",
    riskScore: 97,
    status: "CRITICAL",
    x: 220,
    y: 430,
    details: {
      pan: "ZXCPN8812Q",
      applicationRef: "PN-2026-0988",
      triggeredRules: ["FR-SHA256-IMAGE-COLLISION", "FR-SYNTHETIC-IDENTITY"],
      linkedEntityIds: ["doc-1"],
    },
  },
];

const INITIAL_EDGES: FraudEdge[] = [
  { from: "app-1", to: "bank-1", type: "mule_account", label: "Shared Bank Payout" },
  { from: "app-2", to: "bank-1", type: "mule_account", label: "Shared Bank Payout" },
  { from: "app-3", to: "bank-1", type: "mule_account", label: "Shared Bank Payout" },
  { from: "app-1", to: "phone-1", type: "contact_stack", label: "Stacked Mobile" },
  { from: "app-3", to: "phone-1", type: "contact_stack", label: "Stacked Mobile" },
  { from: "app-4", to: "phone-1", type: "contact_stack", label: "Stacked Mobile" },
  { from: "app-2", to: "doc-1", type: "doc_duplicate", label: "Identical PAN Image" },
  { from: "app-5", to: "doc-1", type: "doc_duplicate", label: "Identical PAN Image" },
];

export default function FraudGraphPage() {
  return (
    <RequirePermission permission="application:review">
      <FraudGraphInner />
    </RequirePermission>
  );
}

function FraudGraphInner() {
  const [nodes, setNodes] = useState<FraudNode[]>(INITIAL_NODES);
  const [selectedNodeId, setSelectedNodeId] = useState<string>("bank-1");
  const [filterType, setFilterType] = useState<string>("ALL");
  const [frozenRings, setFrozenRings] = useState<boolean>(false);
  const [sweepNotice, setSweepNotice] = useState<string | null>(null);

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) ?? nodes[0];

  const handleSweep = () => {
    setSweepNotice("Running cross-application graph traversal across 600 applications...");
    setTimeout(() => {
      setSweepNotice("✓ Sweep complete: 3 suspicious entity clusters isolated · 0 new rings detected.");
    }, 900);
  };

  const handleFreezeRing = () => {
    setFrozenRings(true);
    setNodes((prev) =>
      prev.map((n) => (n.status === "CRITICAL" ? { ...n, status: "RESOLVED" } : n))
    );
  };

  const filteredEdges = INITIAL_EDGES.filter((edge) => {
    if (filterType === "ALL") return true;
    if (filterType === "MULE") return edge.type === "mule_account";
    if (filterType === "PHONE") return edge.type === "contact_stack";
    if (filterType === "DOC") return edge.type === "doc_duplicate";
    return true;
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Cross-Application Fraud Ring & Syndicate Link Analysis"
        description="Graph intelligence engine detecting mule bank account collisions, phone stacking, and duplicate document hashes across disparate candidate applications."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={handleSweep}
              className="gap-1.5"
            >
              <RefreshCw className="h-3.5 w-3.5" /> Run Syndicate Sweep
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              onClick={handleFreezeRing}
              disabled={frozenRings}
              className={clsx(
                "gap-1.5 shadow-sm",
                frozenRings
                  ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                  : "bg-rose-600 hover:bg-rose-700 text-white"
              )}
            >
              <Lock className="h-3.5 w-3.5" />
              {frozenRings ? "Rings Frozen & Payouts Blocked" : "Freeze 3 Flagged Rings"}
            </Button>
          </div>
        }
      />

      <ReviewPortalTabs />

      {/* Real-time KPI Ribbon */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">
            Monitored Dossiers
          </span>
          <p className="mt-1 text-2xl font-extrabold text-slate-900">600</p>
          <p className="text-[11px] text-emerald-600 font-medium">100% Graph Indexed</p>
        </div>

        <div className="rounded-xl border border-rose-200 bg-rose-50/50 p-4 shadow-2xs">
          <span className="text-[11px] font-medium text-rose-700 uppercase tracking-wider">
            Active Syndicate Rings
          </span>
          <p className="mt-1 text-2xl font-extrabold text-rose-700">3 Rings</p>
          <p className="text-[11px] text-rose-600 font-medium">
            {frozenRings ? "✓ Frozen & Locked" : "Immediate Action Needed"}
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">
            Mule Bank Accounts
          </span>
          <p className="mt-1 text-2xl font-extrabold text-blue-700">1 Account</p>
          <p className="text-[11px] text-slate-500">Shared across 3 PANs</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">
            Contact Stacking
          </span>
          <p className="mt-1 text-2xl font-extrabold text-purple-700">1 Cluster</p>
          <p className="text-[11px] text-slate-500">3 Applications on 1 SIM</p>
        </div>

        <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4 shadow-2xs col-span-2 lg:col-span-1">
          <span className="text-[11px] font-medium text-emerald-800 uppercase tracking-wider">
            Protected Payouts
          </span>
          <p className="mt-1 text-2xl font-extrabold text-emerald-800">₹14.8 L</p>
          <p className="text-[11px] text-emerald-700 font-medium">Zero Commission Leakage</p>
        </div>
      </div>

      {sweepNotice && (
        <Alert tone="info">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-brand-600 animate-pulse" />
            <span>{sweepNotice}</span>
          </div>
        </Alert>
      )}

      {/* Main Graph & Entity Inspection Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Interactive Graph Canvas */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 bg-white px-4 py-2.5 rounded-xl border border-slate-200">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
              <Filter className="h-3.5 w-3.5 text-slate-400" />
              <span>Collision Type:</span>
            </div>
            <div className="flex flex-wrap gap-1.5 text-xs">
              {[
                { id: "ALL", label: "All Rings" },
                { id: "MULE", label: "Mule Bank Collisions" },
                { id: "PHONE", label: "Contact Stacking" },
                { id: "DOC", label: "Document Image Clones" },
              ].map((btn) => (
                <button
                  key={btn.id}
                  type="button"
                  onClick={() => setFilterType(btn.id)}
                  className={clsx(
                    "px-2.5 py-1 rounded-lg font-medium transition",
                    filterType === btn.id
                      ? "bg-slate-900 text-white"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                  )}
                >
                  {btn.label}
                </button>
              ))}
            </div>
          </div>

          <div className="relative h-[480px] w-full rounded-2xl border border-slate-800 bg-slate-950 overflow-hidden shadow-xl select-none">
            {/* Grid background effect */}
            <div
              className="absolute inset-0 opacity-20 pointer-events-none"
              style={{
                backgroundImage: "radial-gradient(#38bdf8 1px, transparent 1px)",
                backgroundSize: "24px 24px",
              }}
            />

            {/* SVG Connecting Edges */}
            <svg className="absolute inset-0 h-full w-full pointer-events-none">
              <defs>
                <linearGradient id="edge-mule" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#ef4444" stopOpacity="0.8" />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.8" />
                </linearGradient>
                <linearGradient id="edge-phone" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#a855f7" stopOpacity="0.8" />
                  <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.8" />
                </linearGradient>
              </defs>

              {filteredEdges.map((e, idx) => {
                const fromNode = nodes.find((n) => n.id === e.from);
                const toNode = nodes.find((n) => n.id === e.to);
                if (!fromNode || !toNode) return null;

                const isConnectedToSelected =
                  e.from === selectedNodeId || e.to === selectedNodeId;

                return (
                  <g key={idx}>
                    <line
                      x1={fromNode.x}
                      y1={fromNode.y}
                      x2={toNode.x}
                      y2={toNode.y}
                      stroke={
                        isConnectedToSelected
                          ? "#38bdf8"
                          : e.type === "mule_account"
                          ? "url(#edge-mule)"
                          : "#a855f7"
                      }
                      strokeWidth={isConnectedToSelected ? 3 : 1.5}
                      strokeDasharray={isConnectedToSelected ? "none" : "4 2"}
                      opacity={isConnectedToSelected ? 1 : 0.6}
                    />
                    <circle
                      cx={(fromNode.x + toNode.x) / 2}
                      cy={(fromNode.y + toNode.y) / 2}
                      r="3"
                      fill={isConnectedToSelected ? "#38bdf8" : "#f43f5e"}
                      className="animate-ping"
                    />
                  </g>
                );
              })}
            </svg>

            {/* Interactive Graph Nodes */}
            {nodes.map((node) => {
              const isSelected = node.id === selectedNodeId;

              const getIcon = () => {
                if (node.type === "applicant") return <UserX className="h-4 w-4" />;
                if (node.type === "bank") return <Building2 className="h-4 w-4" />;
                if (node.type === "phone") return <PhoneCall className="h-4 w-4" />;
                return <FileCheck2 className="h-4 w-4" />;
              };

              return (
                <div
                  key={node.id}
                  onClick={() => setSelectedNodeId(node.id)}
                  style={{ left: `${node.x}px`, top: `${node.y}px` }}
                  className={clsx(
                    "absolute -translate-x-1/2 -translate-y-1/2 cursor-pointer transition-all duration-200 group flex flex-col items-center",
                    isSelected ? "scale-110 z-20" : "hover:scale-105 z-10"
                  )}
                >
                  <div
                    className={clsx(
                      "flex h-11 w-11 items-center justify-center rounded-2xl shadow-lg border text-white transition",
                      node.type === "bank"
                        ? "bg-blue-600 border-blue-400"
                        : node.type === "phone"
                        ? "bg-purple-600 border-purple-400"
                        : node.type === "doc_hash"
                        ? "bg-amber-600 border-amber-400"
                        : node.status === "CRITICAL"
                        ? "bg-rose-600 border-rose-400"
                        : "bg-emerald-600 border-emerald-400",
                      isSelected && "ring-4 ring-cyan-400 ring-offset-2 ring-offset-slate-950"
                    )}
                  >
                    {getIcon()}
                  </div>

                  <span
                    className={clsx(
                      "mt-1.5 rounded-md px-2 py-0.5 text-[10px] font-bold tracking-tight whitespace-nowrap shadow-sm border",
                      isSelected
                        ? "bg-cyan-950 border-cyan-400 text-cyan-200"
                        : "bg-slate-900/90 border-slate-700 text-slate-300"
                    )}
                  >
                    {node.label}
                  </span>
                </div>
              );
            })}

            {/* Bottom Graph Legend */}
            <div className="absolute bottom-3 left-3 right-3 flex flex-wrap items-center justify-between gap-2 bg-slate-900/90 backdrop-blur-md px-4 py-2 rounded-xl border border-slate-800 text-[11px] text-slate-300">
              <div className="flex items-center gap-4">
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-rose-500" /> Candidate
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-blue-500" /> Bank Payout Node
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-purple-500" /> Mobile SIM Node
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-amber-500" /> Document Hash
                </span>
              </div>
              <span className="text-slate-400">Click any entity node to inspect links</span>
            </div>
          </div>
        </div>

        {/* Right 1 Col: Entity Inspector Drawer */}
        <div>
          <Card className="p-5 space-y-4 border-slate-200 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div className="flex items-center gap-2">
                <ShieldAlert className="h-5 w-5 text-rose-600" />
                <h3 className="text-sm font-bold text-slate-900">Entity Link Dossier</h3>
              </div>
              <Badge tone={selectedNode.status === "CRITICAL" ? "danger" : "warning"}>
                {selectedNode.status} · Risk {selectedNode.riskScore}/100
              </Badge>
            </div>

            <div>
              <span className="text-xs text-slate-500">Selected Node</span>
              <h2 className="text-lg font-bold text-slate-900">{selectedNode.label}</h2>
              <span className="text-xs font-mono text-slate-500 uppercase tracking-wide">
                Type: {selectedNode.type.toUpperCase()}
              </span>
            </div>

            {/* Entity metadata */}
            <div className="rounded-xl bg-slate-50 p-3 text-xs space-y-2 border border-slate-200">
              {selectedNode.details.pan && (
                <div className="flex justify-between">
                  <span className="text-slate-500">PAN Number:</span>
                  <span className="font-mono font-bold text-slate-900">
                    {selectedNode.details.pan}
                  </span>
                </div>
              )}
              {selectedNode.details.account && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Bank Account:</span>
                  <span className="font-mono font-bold text-slate-900">
                    {selectedNode.details.account}
                  </span>
                </div>
              )}
              {selectedNode.details.bankName && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Bank & Branch:</span>
                  <span className="text-slate-900 font-medium">
                    {selectedNode.details.bankName}
                  </span>
                </div>
              )}
              {selectedNode.details.phone && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Contact Number:</span>
                  <span className="font-mono font-bold text-slate-900">
                    {selectedNode.details.phone}
                  </span>
                </div>
              )}
              {selectedNode.details.hash && (
                <div>
                  <span className="text-slate-500 block">SHA-256 Digest:</span>
                  <span className="font-mono text-[10px] break-all text-slate-700">
                    {selectedNode.details.hash}
                  </span>
                </div>
              )}
              {selectedNode.details.applicationRef && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Application Ref:</span>
                  <span className="font-bold text-brand-700">
                    {selectedNode.details.applicationRef}
                  </span>
                </div>
              )}
            </div>

            {/* Triggered Rule Violations */}
            <div>
              <span className="text-xs font-semibold text-slate-800 block mb-1.5">
                Deterministic Rule Violations:
              </span>
              <ul className="space-y-1.5">
                {selectedNode.details.triggeredRules.map((rule, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-1.5 rounded-lg bg-rose-50 border border-rose-200 p-2 text-xs text-rose-900"
                  >
                    <AlertTriangle className="h-3.5 w-3.5 text-rose-600 shrink-0 mt-0.5" />
                    <span className="font-mono text-[11px] font-semibold">{rule}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Direct Connected Dossiers */}
            <div>
              <span className="text-xs font-semibold text-slate-800 block mb-1.5">
                Associated Application Dossiers:
              </span>
              <div className="space-y-1.5">
                {selectedNode.details.linkedEntityIds.map((linkId) => {
                  const linkedNode = nodes.find((n) => n.id === linkId);
                  if (!linkedNode) return null;
                  return (
                    <div
                      key={linkId}
                      className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-2 text-xs hover:border-slate-300"
                    >
                      <div>
                        <p className="font-bold text-slate-900">{linkedNode.label}</p>
                        <p className="text-[10px] text-slate-500">
                          {linkedNode.details.applicationRef ?? linkedNode.type}
                        </p>
                      </div>
                      <Link
                        href="/app/review"
                        className="inline-flex items-center gap-1 text-[11px] font-semibold text-brand-700 hover:text-brand-800"
                      >
                        Inspect <ArrowRight className="h-3 w-3" />
                      </Link>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Quick Actions */}
            <div className="pt-2 border-t border-slate-100 flex flex-col gap-2">
              <Button
                type="button"
                variant="primary"
                size="sm"
                className="w-full bg-rose-600 hover:bg-rose-700 text-white font-medium text-xs py-2"
                onClick={() => alert(`Locked commission payouts and flagged ${selectedNode.label} for physical verification.`)}
              >
                <Lock className="h-3.5 w-3.5 mr-1.5" /> Lock Payouts & Freeze Entity
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="w-full text-xs py-2"
                onClick={() => alert("Dossier exported to PDF for compliance reporting.")}
              >
                <DownloadCloud className="h-3.5 w-3.5 mr-1.5" /> Export Incident Report
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
