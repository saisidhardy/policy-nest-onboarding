import { INDIAN_STATES } from "@/lib/constants";
import type { ApplicationDetail, ApplicationVerificationReport, DocumentExtraction, DocumentType } from "@/lib/types";

export interface AutofillFieldItem {
  key: keyof ApplicationDetail | "account_number";
  label: string;
  value: string | number;
  source: string;
}

export interface AutofillSuggestion {
  patch: Record<string, string | number | boolean>;
  appliedFields: AutofillFieldItem[];
}

const PAN_RE = /^[A-Z]{5}[0-9]{4}[A-Z]$/;
const PINCODE_RE = /^[1-9][0-9]{5}$/;
const IFSC_RE = /^[A-Z]{4}0[A-Z0-9]{6}$/;
const BANK_ACC_RE = /^[0-9]{9,18}$/;

const STATE_BY_LOWER = new Map(INDIAN_STATES.map((s) => [s.toLowerCase(), s]));
const STATE_ALIASES: Record<string, string> = {
  orissa: "Odisha",
  pondicherry: "Puducherry",
  "nct of delhi": "Delhi",
  "new delhi": "Delhi",
  uttaranchal: "Uttarakhand",
  "jammu & kashmir": "Jammu and Kashmir",
  "daman & diu": "Dadra and Nagar Haveli and Daman and Diu",
  "dadra & nagar haveli": "Dadra and Nagar Haveli and Daman and Diu",
  "andaman & nicobar": "Andaman and Nicobar Islands",
  "andaman & nicobar islands": "Andaman and Nicobar Islands",
  ap: "Andhra Pradesh",
  ts: "Telangana",
  tg: "Telangana",
  ka: "Karnataka",
  mh: "Maharashtra",
  tn: "Tamil Nadu",
  kl: "Kerala",
  gj: "Gujarat",
  rj: "Rajasthan",
  up: "Uttar Pradesh",
  mp: "Madhya Pradesh",
  wb: "West Bengal",
  dl: "Delhi",
  hr: "Haryana",
  pb: "Punjab",
  br: "Bihar",
};

function cleanStr(v: unknown, maxLen = 200): string | null {
  if (typeof v !== "string") return null;
  const cleaned = v.replace(/\s+/g, " ").trim();
  if (!cleaned || cleaned.length > maxLen) return null;
  return cleaned;
}

export function normalizeDobForPatch(raw: unknown): string | null {
  const s = cleanStr(raw, 32);
  if (!s) return null;

  let year: number;
  let month: number;
  let day: number;

  const iso = /^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/.exec(s);
  const dmy = /^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$/.exec(s);
  if (iso) {
    year = Number(iso[1]);
    month = Number(iso[2]);
    day = Number(iso[3]);
  } else if (dmy) {
    day = Number(dmy[1]);
    month = Number(dmy[2]);
    year = Number(dmy[3]);
  } else {
    return null;
  }

  const currentYear = new Date().getFullYear();
  if (year < 1920 || year >= currentYear || month < 1 || month > 12 || day < 1 || day > 31) {
    return null;
  }
  const dt = new Date(Date.UTC(year, month - 1, day));
  if (dt.getUTCFullYear() !== year || dt.getUTCMonth() !== month - 1 || dt.getUTCDate() !== day) {
    return null;
  }
  return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function normalizeIndianStateForPatch(raw: unknown): string | null {
  const s = cleanStr(raw, 80);
  if (!s) return null;
  const lower = s.toLowerCase();
  if (STATE_BY_LOWER.has(lower)) return STATE_BY_LOWER.get(lower)!;
  if (STATE_ALIASES[lower]) return STATE_ALIASES[lower];
  return null;
}

function normalizeGenderForPatch(raw: unknown): string | null {
  const s = cleanStr(raw, 32)?.toUpperCase();
  if (!s) return null;
  if (s === "M" || s === "MALE") return "MALE";
  if (s === "F" || s === "FEMALE") return "FEMALE";
  if (s === "T" || s === "OTHER" || s === "TRANSGENDER") return "OTHER";
  if (s === "PREFER_NOT_TO_SAY") return "PREFER_NOT_TO_SAY";
  return null;
}

function normalizeAadhaarLast4(raw: unknown): string | null {
  const s = cleanStr(raw, 40);
  if (!s) return null;
  const digits = s.replace(/\D/g, "");
  if (digits.length >= 4) {
    return digits.slice(-4);
  }
  return null;
}

function normalizeResultStatus(raw: unknown): string | null {
  const s = cleanStr(raw, 32)?.toUpperCase();
  if (!s) return null;
  if (s === "PASS" || s === "PASSED") return "PASS";
  if (s === "FAIL" || s === "FAILED") return "FAIL";
  if (s === "AWAITING" || s === "APPEARING") return "AWAITING";
  return null;
}

function pickField(ext: DocumentExtraction | undefined, ...keys: string[]): string | null {
  if (!ext) return null;
  const source = ext.effective_fields ?? ext.extracted_fields ?? {};
  for (const key of keys) {
    const val = cleanStr(source[key], 255);
    if (val) return val;
  }
  return null;
}

function splitAddressLine(summary: string): { line1: string; line2: string | null } {
  const cleaned = summary.replace(/\s+/g, " ").trim();
  if (cleaned.length <= 120) {
    return { line1: cleaned, line2: null };
  }
  const splitAt = cleaned.lastIndexOf(",", 115);
  const cut = splitAt > 30 ? splitAt : 115;
  return {
    line1: cleaned.slice(0, cut).trim(),
    line2: cleaned.slice(cut).replace(/^,\s*/, "").trim().slice(0, 120) || null,
  };
}

export function extractAutofillFromReport(
  application: ApplicationDetail,
  report: ApplicationVerificationReport | null
): AutofillSuggestion {
  const patch: Record<string, string | number | boolean> = {};
  const appliedFields: AutofillFieldItem[] = [];

  if (!report) return { patch, appliedFields };

  const byDoc = new Map<DocumentType, DocumentExtraction>();
  for (const ext of report.extractions) {
    byDoc.set(ext.doc_type, ext);
  }

  const panExt = byDoc.get("PAN_CARD");
  const afExt = byDoc.get("AADHAAR_FRONT");
  const abExt = byDoc.get("AADHAAR_BACK");
  const markExt = byDoc.get("CLASS_10_MARKSHEET");
  const bankExt = byDoc.get("BANK_DOCUMENT");

  const setIfEmpty = (
    key: keyof ApplicationDetail | "account_number",
    label: string,
    candidate: string | number | null,
    source: string
  ) => {
    if (candidate === null || candidate === undefined || candidate === "") return;
    if (patch[key] !== undefined) return;
    if (key === "account_number") {
      if (application.has_account_number) return;
    } else {
      const existing = application[key];
      if (existing !== null && existing !== undefined && String(existing).trim() !== "") {
        return;
      }
    }
    patch[key] = candidate;
    appliedFields.push({ key, label, value: candidate, source });
  };

  // Personal fields (prefer Aadhaar Front / PAN / Marksheet)
  const fullName =
    pickField(afExt, "full_name", "name") ??
    pickField(panExt, "full_name", "name") ??
    pickField(markExt, "full_name", "student_name") ??
    pickField(bankExt, "account_holder_name");
  if (fullName && fullName.length >= 2) {
    setIfEmpty("full_name", "Full name", fullName, afExt ? "Aadhaar Front" : panExt ? "PAN Card" : "Marksheet");
  }

  const fatherName =
    pickField(panExt, "father_or_spouse_name", "father_name") ??
    pickField(abExt, "father_or_spouse_name", "care_of") ??
    pickField(afExt, "father_or_spouse_name");
  if (fatherName && fatherName.length >= 2) {
    setIfEmpty("father_or_spouse_name", "Father / spouse name", fatherName, panExt ? "PAN Card" : "Aadhaar");
  }

  const dob =
    normalizeDobForPatch(pickField(panExt, "date_of_birth", "dob")) ??
    normalizeDobForPatch(pickField(afExt, "date_of_birth", "dob")) ??
    normalizeDobForPatch(pickField(markExt, "date_of_birth", "dob"));
  setIfEmpty("date_of_birth", "Date of birth", dob, panExt ? "PAN Card" : afExt ? "Aadhaar Front" : "Marksheet");

  const gender = normalizeGenderForPatch(pickField(afExt, "gender"));
  setIfEmpty("gender", "Gender", gender, "Aadhaar Front");

  const panRaw = pickField(panExt, "pan_number", "pan")?.toUpperCase() ?? null;
  if (panRaw && PAN_RE.test(panRaw)) {
    setIfEmpty("pan_number", "PAN number", panRaw, "PAN Card");
  }

  const aadhaarLast4 =
    normalizeAadhaarLast4(pickField(afExt, "aadhaar_last4", "aadhaar_number")) ??
    normalizeAadhaarLast4(pickField(abExt, "aadhaar_last4", "aadhaar_number"));
  setIfEmpty("aadhaar_last4", "Aadhaar last 4 digits", aadhaarLast4, afExt ? "Aadhaar Front" : "Aadhaar Back");

  // Address fields (from Aadhaar Back)
  const rawAddr =
    pickField(abExt, "address_line1") ?? pickField(abExt, "address_summary", "address");
  if (rawAddr && rawAddr.length >= 5) {
    const split = splitAddressLine(rawAddr);
    setIfEmpty("address_line1", "Address line 1", split.line1, "Aadhaar Back");
    const explicitLine2 = pickField(abExt, "address_line2");
    setIfEmpty("address_line2", "Address line 2", explicitLine2 ?? split.line2, "Aadhaar Back");
  }
  setIfEmpty("city", "City", pickField(abExt, "city"), "Aadhaar Back");
  setIfEmpty("district", "District", pickField(abExt, "district"), "Aadhaar Back");

  const normState = normalizeIndianStateForPatch(pickField(abExt, "state"));
  setIfEmpty("state", "State", normState, "Aadhaar Back");

  const pinRaw = pickField(abExt, "pincode");
  if (pinRaw && PINCODE_RE.test(pinRaw)) {
    setIfEmpty("pincode", "PIN code", pinRaw, "Aadhaar Back");
  }

  // Education fields (Class 10 Marksheet)
  if (markExt) {
    setIfEmpty("education_level", "Highest education", "CLASS_10", "Class 10 Marksheet");
    setIfEmpty("board_name", "Education board", pickField(markExt, "board_name", "board"), "Class 10 Marksheet");
    setIfEmpty("school_or_university", "School", pickField(markExt, "school_or_university", "school"), "Class 10 Marksheet");
    const yearStr = pickField(markExt, "passing_year", "year");
    if (yearStr && /^\d{4}$/.test(yearStr)) {
      const yr = Number(yearStr);
      if (yr >= 1950 && yr <= 2030) {
        setIfEmpty("passing_year", "Passing year", yr, "Class 10 Marksheet");
      }
    }
    setIfEmpty("roll_number", "Roll number", pickField(markExt, "roll_number"), "Class 10 Marksheet");
    setIfEmpty("result_status", "Result status", normalizeResultStatus(pickField(markExt, "result_status", "result")) ?? "PASS", "Class 10 Marksheet");
    setIfEmpty("percentage_or_cgpa", "Marks / CGPA", pickField(markExt, "percentage_or_cgpa", "percentage", "cgpa"), "Class 10 Marksheet");
  }

  // Bank fields (from Bank Document + IFSC lookup check)
  const holderName = pickField(bankExt, "account_holder_name") ?? fullName;
  if (holderName && holderName.length >= 2) {
    setIfEmpty("account_holder_name", "Account holder name", holderName, bankExt ? "Bank Document" : "KYC Doc");
  }

  const ifscRaw = pickField(bankExt, "ifsc_code", "ifsc")?.toUpperCase() ?? null;
  if (ifscRaw && IFSC_RE.test(ifscRaw)) {
    setIfEmpty("ifsc_code", "IFSC code", ifscRaw, "Bank Document");
  }

  const ifscCheck = report.checks.find(
    (c) => (c.check_type === "EXTERNAL_IFSC_DIRECTORY" || c.check_type === "IFSC_LOOKUP") && c.status === "PASSED"
  );
  const ifscBank = cleanStr(ifscCheck?.details?.bank, 128);
  const ifscBranch = cleanStr(ifscCheck?.details?.branch, 128);
  setIfEmpty("bank_name", "Bank name", ifscBank ?? pickField(bankExt, "bank_name"), ifscBank ? "RBI IFSC Directory" : "Bank Document");
  setIfEmpty("branch_name", "Branch name", ifscBranch ?? pickField(bankExt, "branch_name"), ifscBranch ? "RBI IFSC Directory" : "Bank Document");

  const accRaw = pickField(bankExt, "account_number")?.replace(/[\s-]/g, "") ?? null;
  if (accRaw && BANK_ACC_RE.test(accRaw)) {
    setIfEmpty("account_number", "Account number", accRaw, "Bank Document");
  }

  return { patch, appliedFields };
}
