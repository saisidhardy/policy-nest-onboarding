import type { DocumentType } from "./types";

export interface RuleReference {
  code: string;
  title: string;
  summary: string;
  source: string;
}

export interface DocumentRequirement {
  type: DocumentType;
  applicantLabel: string;
  shortLabel: string;
  stepNumber: number;
  purpose: string;
  whyNeeded: string;
  mustShow: string[];
  photoGuidance: string[];
  acceptedFormats: string[];
  maxSizeBytes: number;
  commonProblems: string[];
  rejectionConditions: string[];
  correctionExamples: string[];
  humanReviewConditions: string[];
  privacyNotes: string[];
  ruleReferences: RuleReference[];
}

export const DOCUMENT_GUIDANCE_MAP: Record<DocumentType, DocumentRequirement> = {
  PAN_CARD: {
    type: "PAN_CARD",
    applicantLabel: "Permanent Account Number (PAN) Card",
    shortLabel: "PAN Card",
    stepNumber: 1,
    purpose: "Statutory tax identification and primary identity verification under IRDAI POSP Guidelines.",
    whyNeeded: "IRDAI mandates a valid individual PAN to issue a POSP appointment and process commission payouts.",
    mustShow: [
      "Full applicant name matching your registration",
      "Father's name (or eligible guardian name)",
      "Complete Date of Birth (DD/MM/YYYY)",
      "10-character alphanumeric PAN number (e.g. ABCDE1234F)",
      "Clear photo and signature area",
      "Income Tax Department emblem and hologram",
    ],
    photoGuidance: [
      "Place card flat on a dark, non-reflective background",
      "Ensure all 4 corners and borders are clearly inside the frame",
      "Turn camera flash OFF to avoid blinding glare on laminated cards",
      "Shoot in natural daylight or bright, even room light",
      "Do not hold the card with fingers covering any letters or numbers",
    ],
    acceptedFormats: ["JPG", "JPEG", "PNG", "WebP", "PDF"],
    maxSizeBytes: 10 * 1024 * 1024,
    commonProblems: [
      "Flash glare reflecting on the card surface and washing out the PAN number",
      "Uploading a business/firm PAN (4th character 'F', 'C', 'T') instead of individual ('P')",
      "Cropped edges or missing corners from tight camera zoom",
      "Blurred photo or low-resolution thumbnail",
    ],
    rejectionConditions: [
      "Business, partnership, or trust PAN cards (POSP requires individual 'P' PAN)",
      "Tampered, altered, or forged card images",
      "Completely illegible text where the 10-character PAN cannot be determined",
    ],
    correctionExamples: [
      "If your photo was blurry, retake the photo under a desk lamp or near a window without flash.",
      "If the edges were cropped, pull the camera back 6 inches to capture the full card borders.",
    ],
    humanReviewConditions: [
      "Spelling variation between PAN and Aadhaar/Marksheet (reviewed under 8-Tier Name Matching)",
      "Initials or middle name differences (e.g., 'R. Sharma' vs 'Rajesh Sharma')",
      "NSDL/UTIITSL verification timeout or registry latency",
    ],
    privacyNotes: [
      "Your PAN is used solely for IRDAI registry verification and TDS tax compliance.",
      "Images are stored in AES-256 encrypted private cloud storage.",
      "PAN details are never shared with marketing or third-party lead brokers.",
    ],
    ruleReferences: [
      {
        code: "IRDAI-POSP-2016-SEC3",
        title: "Mandatory Individual PAN Verification",
        summary: "Candidate must hold a valid personal PAN card issued by Income Tax Dept.",
        source: "IRDAI (Registration of Insurance Marketing Firm) Regulations & POSP Guidelines",
      },
    ],
  },

  AADHAAR_FRONT: {
    type: "AADHAAR_FRONT",
    applicantLabel: "Aadhaar Card (Front Side)",
    shortLabel: "Aadhaar Front",
    stepNumber: 2,
    purpose: "Primary demographic identity and date of birth proof.",
    whyNeeded: "Confirms your legal identity, photograph, and date of birth match your PAN and application.",
    mustShow: [
      "Applicant's legal full name",
      "Date of Birth (or Year of Birth if older issue)",
      "Gender (Male / Female / Transgender)",
      "Clear facial portrait",
      "Government of India / UIDAI header",
    ],
    photoGuidance: [
      "Capture the FRONT side showing your photograph and name",
      "Place on a solid surface and shoot directly from above",
      "Keep flash off to prevent specular reflection over the photo",
      "Make sure name and date of birth are razor-sharp and legible",
    ],
    acceptedFormats: ["JPG", "JPEG", "PNG", "WebP", "PDF"],
    maxSizeBytes: 10 * 1024 * 1024,
    commonProblems: [
      "Uploading the back side (address) instead of the front side",
      "Uploading an e-Aadhaar PDF without knowing the password",
      "Finger covering the date of birth or name line",
      "Heavy shadow across the portrait photo",
    ],
    rejectionConditions: [
      "Upload does not show the applicant's photograph or name",
      "Expired mask or illegible copy",
      "Forged or digitally altered identity document",
    ],
    correctionExamples: [
      "If you accidentally uploaded the back side, tap 'Upload a better image' and select the front side with your photo.",
      "If using e-Aadhaar PDF, please ensure it is unprotected or provide a clear photograph of your physical card.",
    ],
    humanReviewConditions: [
      "Aadhaar shows only Year of Birth (YYYY) while application has DD/MM/YYYY",
      "Name order reversed (Surname First vs Surname Last)",
      "Minor regional phoneme variations (e.g., 'Vikas' vs 'Bikash')",
    ],
    privacyNotes: [
      "DPDP Act 2023 & UIDAI compliant: PolicyNest automatically masks the first 8 digits.",
      "Only the last 4 digits (XXXX-XXXX-1234) are retained for audit and verification.",
      "Your full 12-digit Aadhaar number is NEVER stored in database plaintext.",
    ],
    ruleReferences: [
      {
        code: "UIDAI-CIR-2018-MASK",
        title: "Aadhaar Data Minimization & Masking",
        summary: "Mandatory masking of first 8 digits of Aadhaar number across private storage systems.",
        source: "UIDAI Circular on Offline Verification & DPDP Act 2023",
      },
    ],
  },

  AADHAAR_BACK: {
    type: "AADHAAR_BACK",
    applicantLabel: "Aadhaar Card (Back Side / Address)",
    shortLabel: "Aadhaar Back",
    stepNumber: 3,
    purpose: "Authoritative residential address verification.",
    whyNeeded: "Validates your permanent and communication address against registered pincode and state jurisdiction.",
    mustShow: [
      "Complete residential address including House/Street/Locality",
      "City, District, and State",
      "6-digit Postal Pincode",
      "UIDAI barcode or QR code area (if present)",
      "Father's / Husband's / Guardian's name (C/O, S/O, W/O, D/O)",
    ],
    photoGuidance: [
      "Capture the BACK side showing your full residential address and pincode",
      "Ensure all 4 corners of the card are visible",
      "Check that the address text and pincode are crisp and easy to read",
      "Avoid uploading the same front image twice",
    ],
    acceptedFormats: ["JPG", "JPEG", "PNG", "WebP", "PDF"],
    maxSizeBytes: 10 * 1024 * 1024,
    commonProblems: [
      "Accidentally re-uploading the front photo instead of the back address side",
      "Pincode or district name cut off at the bottom or side",
      "Address blurred or smudged from camera motion",
    ],
    rejectionConditions: [
      "Duplicate upload of the front side (flagged automatically by duplicate hash check)",
      "Completely blank or illegible address lines",
    ],
    correctionExamples: [
      "Flip your card over, lay it flat, and take a photo of the address side.",
    ],
    humanReviewConditions: [
      "Address line format differs from postal database but pincode matches",
      "New district reorganization in state jurisdiction",
    ],
    privacyNotes: [
      "Address details are used strictly to verify territorial licensing jurisdiction.",
      "Data is retained in secure storage during your active POSP appointment.",
    ],
    ruleReferences: [
      {
        code: "IRDAI-POSP-ADDRESS-MANDATE",
        title: "Jurisdictional Address Verification",
        summary: "POSP candidate must provide proof of residence within Indian territory.",
        source: "IRDAI POSP Appointment Guidelines",
      },
    ],
  },

  CLASS_10_MARKSHEET: {
    type: "CLASS_10_MARKSHEET",
    applicantLabel: "Class 10 Marksheet or Passing Certificate",
    shortLabel: "Class 10 Certificate",
    stepNumber: 4,
    purpose: "Statutory minimum educational qualification proof (Matriculation / Secondary School).",
    whyNeeded: "IRDAI regulations require all POSP agents to have completed at least secondary school (Class 10).",
    mustShow: [
      "Candidate's full name",
      "Recognized Examination Board name (CBSE, ICSE, NIOS, or State Board)",
      "Roll number / Registration number",
      "Year of passing",
      "Clear PASS or qualifying status",
      "Official board seal or signature",
    ],
    photoGuidance: [
      "Photograph the full certificate or marksheet unfold on a clean surface",
      "Capture all four edges so the board name at top and signature at bottom are visible",
      "If the certificate has folded creases, gently flatten it to keep text readable",
      "Higher qualifications (Class 12, Degree) are welcome but Class 10 is mandatory for age & education proof",
    ],
    acceptedFormats: ["JPG", "JPEG", "PNG", "WebP", "PDF"],
    maxSizeBytes: 10 * 1024 * 1024,
    commonProblems: [
      "Admit card uploaded instead of final marksheet or passing certificate",
      "Top board header or bottom pass result cropped out",
      "Crease reflection obscuring candidate name or marks",
    ],
    rejectionConditions: [
      "Mark card showing 'FAIL' or 'COMPARTMENT' with no subsequent passing certificate",
      "Unofficial mock exam papers or provisional hall tickets",
    ],
    correctionExamples: [
      "Please upload your official final passing certificate or marksheet, not the exam admit card.",
      "Ensure the word 'PASSED' or qualifying grades are visible on the page.",
    ],
    humanReviewConditions: [
      "National Institute of Open Schooling (NIOS) or State Open School certificates (fully recognized, reviewed by staff)",
      "State secondary boards with non-English or vernacular scripts",
      "Certificate issued in maiden name prior to marriage (reviewed with name-linkage declaration)",
    ],
    privacyNotes: [
      "Marks and grades are used solely to confirm secondary school pass status.",
      "We do not evaluate percentage cutoffs; IRDAI requires only a recognized pass.",
    ],
    ruleReferences: [
      {
        code: "IRDAI-POSP-EDU-2016",
        title: "Minimum Educational Qualification",
        summary: "Applicant must have passed 10th standard from a recognised Central or State examination board.",
        source: "IRDAI Guidelines on Point of Sales Persons §2(a)",
      },
    ],
  },

  BANK_DOCUMENT: {
    type: "BANK_DOCUMENT",
    applicantLabel: "Cancelled Cheque or Bank Passbook / Statement",
    shortLabel: "Bank Proof",
    stepNumber: 5,
    purpose: "Commission payout mandate and bank account verification.",
    whyNeeded: "Insurance commissions can only be transferred to an authenticated account in your name via NEFT/RTGS.",
    mustShow: [
      "Applicant's printed name as primary account holder",
      "Complete Bank Account Number",
      "11-character Indian Financial System Code (IFSC)",
      "Bank name and branch location",
      "If cheque: The word 'CANCELLED' drawn across with two parallel lines without covering details",
    ],
    photoGuidance: [
      "Write 'CANCELLED' across the cheque leaf between two parallel lines",
      "DO NOT write over or cover your printed name, account number, or IFSC",
      "If using a passbook or bank statement, upload the first page showing your name, account number, and IFSC",
      "Digital e-statements downloaded from netbanking (PDF) are accepted and pass faster",
    ],
    acceptedFormats: ["JPG", "JPEG", "PNG", "WebP", "PDF"],
    maxSizeBytes: 10 * 1024 * 1024,
    commonProblems: [
      "Writing 'CANCELLED' directly over the account number or IFSC code",
      "Uploading a parent's, spouse's, or friend's account cheque (strictly prohibited)",
      "Cheque does not have the applicant's name pre-printed on it",
      "Bank statement transaction pages without account header details",
    ],
    rejectionConditions: [
      "Third-party bank account belonging to a different individual",
      "Joint account where the applicant is SECOND or THIRD holder (must be FIRST holder)",
      "Account marked frozen, NRE/NRO, or invalid account number",
    ],
    correctionExamples: [
      "If your cheque leaf did not have your name printed, please upload the first page of your passbook or a recent PDF bank statement.",
      "If you uploaded a joint account, ensure your name appears as the FIRST account holder.",
    ],
    humanReviewConditions: [
      "Joint bank account where candidate is 1st holder (requires manual confirmation)",
      "Cooperative or Gramin bank IFSC codes not yet present in automated NPCI clearing directory",
      "Penny-drop name match score between 75% and 89% (reviewed under 8-tier name protocol)",
    ],
    privacyNotes: [
      "Account details are encrypted and utilized solely for statutory commission disbursements.",
      "PolicyNest never asks for your ATM PIN, NetBanking password, or OTP.",
    ],
    ruleReferences: [
      {
        code: "IRDAI-PAYOUT-BANK-MANDATE",
        title: "Direct Commission Payout to Agent",
        summary: "Commission can only be credited to applicant's own verified bank account.",
        source: "IRDAI (Payment of Commission or Brokerage) Regulations",
      },
    ],
  },

  APPLICANT_SELFIE: {
    type: "APPLICANT_SELFIE",
    applicantLabel: "Live Applicant Photograph (Selfie)",
    shortLabel: "Selfie Portrait",
    stepNumber: 6,
    purpose: "Facial identity confirmation and live liveness verification against PAN/Aadhaar photos.",
    whyNeeded: "Confirms that the person completing the application is the genuine identity document holder.",
    mustShow: [
      "Clear, unobstructed view of your entire face from chin to forehead",
      "Direct eye contact with the camera lens",
      "Neutral facial expression or gentle smile",
      "Even lighting on both sides of your face with no harsh shadows",
    ],
    photoGuidance: [
      "Look straight into the camera lens at eye level",
      "Remove sunglasses, hats, caps, or face masks (prescription glasses are fine)",
      "Stand facing a window or light source; avoid backlighting (light behind you)",
      "Ensure your face fills roughly 60% of the camera circle",
    ],
    acceptedFormats: ["JPG", "JPEG", "PNG", "WebP"],
    maxSizeBytes: 10 * 1024 * 1024,
    commonProblems: [
      "Strong backlighting from a window or light behind the head, making the face dark",
      "Wearing dark sunglasses, sports cap, or mask covering the chin/mouth",
      "Camera held too close causing fish-eye distortion or cropped forehead",
      "Blurred photo due to moving while taking the shot",
    ],
    rejectionConditions: [
      "Uploading a photo of a photograph or computer screen instead of a live camera photo",
      "Face covered by mask, sunglasses, or heavy distortion",
      "Severe facial mismatch against PAN/Aadhaar identity documents",
    ],
    correctionExamples: [
      "Face a window in daylight, take off any cap or sunglasses, and hold the phone steady at eye level.",
    ],
    humanReviewConditions: [
      "Facial comparison confidence score between 70% and 85% due to aging compared to older PAN card",
      "Recent change in appearance (beard, religious headwear, turban)",
    ],
    privacyNotes: [
      "Used strictly for 1:1 facial identity matching against government identity documents.",
      "Biometric templates are processed in transient secure memory and never sold or shared.",
    ],
    ruleReferences: [
      {
        code: "IRDAI-KYC-FACE-MATCH",
        title: "Applicant Photo Verification & Liveness",
        summary: "Insurer must verify applicant likeness against government-issued photo identity proof.",
        source: "IRDAI Master Circular on Know Your Customer (KYC)",
      },
    ],
  },
};

/**
 * Plain-Language Applicant-Safe Status Mapping
 * Translates technical internal workflow constants into friendly, reassuring applicant updates.
 */
export interface ApplicantSafeStatusInfo {
  code: string;
  applicantLabel: string;
  tone: "neutral" | "brand" | "success" | "warning" | "danger";
  summary: string;
  actionRequired: boolean;
  actionLabel?: string;
  whatHappensNext: string;
}

export const APPLICANT_SAFE_STATUS_MAP: Record<string, ApplicantSafeStatusInfo> = {
  DRAFT: {
    code: "DRAFT",
    applicantLabel: "Application in progress",
    tone: "neutral",
    summary: "Your progress is saved securely. You can complete the remaining sections whenever you are ready.",
    actionRequired: true,
    actionLabel: "Continue application",
    whatHappensNext: "Complete all sections and upload your 6 documents to submit.",
  },
  SUBMITTED: {
    code: "SUBMITTED",
    applicantLabel: "Application submitted",
    tone: "brand",
    summary: "We have received your application and all documents. Automatic verification has begun.",
    actionRequired: false,
    whatHappensNext: "Automated checks run within minutes. You do not need to do anything right now.",
  },
  IN_REVIEW: {
    code: "IN_REVIEW",
    applicantLabel: "Sent to a reviewer",
    tone: "warning",
    summary: "A human reviewer is reviewing your documents to ensure every detail complies with IRDAI guidelines.",
    actionRequired: false,
    whatHappensNext: "Reviewers typically complete checks within 24–48 hours. We will notify you via SMS and WhatsApp.",
  },
  NEEDS_MORE_INFO: {
    code: "NEEDS_MORE_INFO",
    applicantLabel: "Correction required",
    tone: "warning",
    summary: "One or more documents need a clearer photo or updated detail before your application can proceed.",
    actionRequired: true,
    actionLabel: "Fix required items",
    whatHappensNext: "Review the specific remarks on each flagged document and upload a clearer photo. Verified documents are kept intact.",
  },
  REWORK_SUBMITTED: {
    code: "REWORK_SUBMITTED",
    applicantLabel: "Updated documents under review",
    tone: "brand",
    summary: "Thank you for submitting your updated documents. Our review team is verifying the changes.",
    actionRequired: false,
    whatHappensNext: "Updated documents receive expedited re-check within 1 business day.",
  },
  KYC_APPROVED: {
    code: "KYC_APPROVED",
    applicantLabel: "Verified automatically",
    tone: "success",
    summary: "All your identity, qualification, and bank records have been verified successfully!",
    actionRequired: true,
    actionLabel: "Start POSP training",
    whatHappensNext: "You can now begin your 15-hour POSP training modules.",
  },
  REJECTED: {
    code: "REJECTED",
    applicantLabel: "Eligibility review completed",
    tone: "danger",
    summary: "Your application could not be verified automatically against statutory eligibility requirements.",
    actionRequired: true,
    actionLabel: "View details or appeal",
    whatHappensNext: "If you believe this was an error (such as a name spelling variation or joint account), you have the statutory right to raise a formal appeal for human review.",
  },
  WITHDRAWN: {
    code: "WITHDRAWN",
    applicantLabel: "Application withdrawn",
    tone: "neutral",
    summary: "This application was withdrawn at your request.",
    actionRequired: false,
    whatHappensNext: "You may start a fresh application whenever you wish.",
  },
  TRAINING_IN_PROGRESS: {
    code: "TRAINING_IN_PROGRESS",
    applicantLabel: "Training in progress",
    tone: "brand",
    summary: "You are currently completing your required 15 hours of IC-38 POSP learning modules.",
    actionRequired: true,
    actionLabel: "Continue training",
    whatHappensNext: "Once all modules reach 100%, your online certification examination unlocks immediately.",
  },
  CERTIFIED: {
    code: "CERTIFIED",
    applicantLabel: "Certified POSP Agent",
    tone: "success",
    summary: "Congratulations! You are officially appointed as a certified Point of Sales Person.",
    actionRequired: false,
    actionLabel: "Download certificate",
    whatHappensNext: "Download your official digital POSP certificate with cryptographic integrity verification.",
  },
};

/**
 * 6-Stage Journey Definition (Workstream F)
 */
export interface JourneyStageMeta {
  stage: number;
  id: string;
  applicantLabel: string;
  technicalLabel: string;
  summary: string;
  regulatoryNote: string;
}

export const JOURNEY_STAGES: JourneyStageMeta[] = [
  {
    stage: 1,
    id: "details",
    applicantLabel: "Your details",
    technicalLabel: "Candidate Intake & Demographic Record",
    summary: "Enter your personal, residential address, education, and bank details.",
    regulatoryNote: "IRDAI POSP Guidelines 2016 §3",
  },
  {
    stage: 2,
    id: "documents",
    applicantLabel: "Documents",
    technicalLabel: "6-Document Compliance Ingestion",
    summary: "Upload clear photos of your 6 required identity and qualification documents.",
    regulatoryNote: "DPDP Act 2023 & UIDAI Circulars",
  },
  {
    stage: 3,
    id: "verification",
    applicantLabel: "Verification",
    technicalLabel: "KYC & Verification Engine",
    summary: "Automated OCR, NSDL PAN verification, bank penny-drop, and human review.",
    regulatoryNote: "PMLA 2002 & IRDAI KYC Master Circular",
  },
  {
    stage: 4,
    id: "training",
    applicantLabel: "Training",
    technicalLabel: "15-Hour POSP IC-38 LMS",
    summary: "Complete 15 hours of interactive POSP training covering Life, General, and Health insurance.",
    regulatoryNote: "IRDAI POSP Mandatory Curriculum",
  },
  {
    stage: 5,
    id: "exam",
    applicantLabel: "Exam",
    technicalLabel: "Online POSP Competency Assessment",
    summary: "Take the 25-question online multiple-choice exam (50% passing score).",
    regulatoryNote: "Statutory POSP Certification Protocol",
  },
  {
    stage: 6,
    id: "certificate",
    applicantLabel: "Certificate",
    technicalLabel: "POSP Appointment & Cryptographic Seal",
    summary: "Receive your official digital POSP appointment certificate with SHA-256 seal.",
    regulatoryNote: "IRDAI Form A POSP Appointment",
  },
];
