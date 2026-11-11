import type { DocumentType } from "./types";

export const INDIAN_STATES: string[] = [
  "Andaman and Nicobar Islands",
  "Andhra Pradesh",
  "Arunachal Pradesh",
  "Assam",
  "Bihar",
  "Chandigarh",
  "Chhattisgarh",
  "Dadra and Nagar Haveli and Daman and Diu",
  "Delhi",
  "Goa",
  "Gujarat",
  "Haryana",
  "Himachal Pradesh",
  "Jammu and Kashmir",
  "Jharkhand",
  "Karnataka",
  "Kerala",
  "Ladakh",
  "Lakshadweep",
  "Madhya Pradesh",
  "Maharashtra",
  "Manipur",
  "Meghalaya",
  "Mizoram",
  "Nagaland",
  "Odisha",
  "Puducherry",
  "Punjab",
  "Rajasthan",
  "Sikkim",
  "Tamil Nadu",
  "Telangana",
  "Tripura",
  "Uttar Pradesh",
  "Uttarakhand",
  "West Bengal",
];

export const WIZARD_STEPS = [
  { step: 1, key: "personal", title: "Personal details", subtitle: "Identity & PAN" },
  { step: 2, key: "address", title: "Address details", subtitle: "Residential & permanent" },
  { step: 3, key: "education", title: "Education details", subtitle: "Class 10 & higher" },
  { step: 4, key: "bank", title: "Bank details", subtitle: "Commission payout" },
  { step: 5, key: "documents", title: "Documents", subtitle: "6 required uploads" },
  { step: 6, key: "review", title: "Review & submit", subtitle: "Verify & declare" },
] as const;

export interface DocumentSpec {
  type: DocumentType;
  label: string;
  description: string;
  accept: string;
  captureCamera?: boolean;
}

export const REQUIRED_DOCUMENTS: DocumentSpec[] = [
  {
    type: "PAN_CARD",
    label: "1. PAN Card",
    description: "Clear photo or PDF of your individual PAN card showing full name, DOB, and PAN number.",
    accept: "image/jpeg,image/png,image/webp,application/pdf",
  },
  {
    type: "AADHAAR_FRONT",
    label: "2. Aadhaar Front",
    description: "Front side of your Aadhaar card. PolicyNest stores only the last 4 digits per UIDAI rules.",
    accept: "image/jpeg,image/png,image/webp,application/pdf",
  },
  {
    type: "AADHAAR_BACK",
    label: "3. Aadhaar Back",
    description: "Back side of your Aadhaar card showing your address.",
    accept: "image/jpeg,image/png,image/webp,application/pdf",
  },
  {
    type: "CLASS_10_MARKSHEET",
    label: "4. Class 10 Marksheet",
    description: "Secondary school passing certificate or marksheet from a recognised board (CBSE, CISCE, NIOS, State Board).",
    accept: "image/jpeg,image/png,image/webp,application/pdf",
  },
  {
    type: "BANK_DOCUMENT",
    label: "5. Cancelled Cheque / Bank Proof",
    description: "Cancelled cheque leaf or first page of bank statement showing account holder name, account number, and IFSC.",
    accept: "image/jpeg,image/png,image/webp,application/pdf",
  },
  {
    type: "APPLICANT_SELFIE",
    label: "6. Applicant Selfie",
    description: "Live portrait photo in good lighting without sunglasses or masks (JPG, PNG, or WebP).",
    accept: "image/jpeg,image/png,image/webp",
    captureCamera: true,
  },
];

export const APPLICATION_STATUS_META: Record<
  string,
  { label: string; tone: "neutral" | "brand" | "success" | "warning" | "danger" }
> = {
  DRAFT: { label: "Draft", tone: "neutral" },
  SUBMITTED: { label: "Submitted", tone: "brand" },
  IN_REVIEW: { label: "In review", tone: "warning" },
  NEEDS_MORE_INFO: { label: "Action needed", tone: "warning" },
  REWORK_SUBMITTED: { label: "Rework submitted", tone: "brand" },
  KYC_APPROVED: { label: "KYC approved", tone: "success" },
  REJECTED: { label: "Rejected", tone: "danger" },
  WITHDRAWN: { label: "Withdrawn", tone: "neutral" },
  TRAINING_IN_PROGRESS: { label: "Training", tone: "brand" },
  CERTIFIED: { label: "Certified POSP", tone: "success" },
};

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}
