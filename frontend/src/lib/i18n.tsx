"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

export type Locale = "en" | "hi";

export interface Translations {
  nav: {
    overview: string;
    onboarding: string;
    myApplications: string;
    review: string;
    analytics: string;
    training: string;
    notifications: string;
    account: string;
    adminUsers: string;
    adminReviewers: string;
    adminApplications: string;
    adminRoles: string;
    adminRules: string;
    adminIntegrations: string;
    adminAudit: string;
    adminSystem: string;
    signOut: string;
  };
  wizard: {
    title: string;
    subtitle: string;
    step0_badge: string;
    step1_title: string;
    step2_title: string;
    step3_title: string;
    step4_title: string;
    step5_title: string;
    step6_title: string;
    saveDraft: string;
    continue: string;
    back: string;
    submit: string;
    submitting: string;
    saving: string;
    draftSaved: string;
    fastTrack: string;
    fastTrackNotice: string;
  };
  docs: {
    title: string;
    subtitle: string;
    pan: string;
    panDesc: string;
    aadhaarFront: string;
    aadhaarFrontDesc: string;
    aadhaarBack: string;
    aadhaarBackDesc: string;
    marksheet: string;
    marksheetDesc: string;
    cheque: string;
    chequeDesc: string;
    selfie: string;
    selfieDesc: string;
    uploadButton: string;
    reuploadButton: string;
    previewButton: string;
    removeButton: string;
    cameraButton: string;
    guidedButton: string;
    qualityOk: string;
    qualityIssue: string;
    dpdpNotice: string;
    dpdpClause: string;
    autofillApplied: string;
    uploadStage1: string;
    uploadStage2: string;
    uploadStage3: string;
    uploadStage4: string;
  };
  camera: {
    title: string;
    close: string;
    takePhoto: string;
    ready: string;
    centerFace: string;
    blinkPrompt: string;
    livenessVerified: string;
    darkAlert: string;
    glareAlert: string;
    activePrompt: string;
  };
  rework: {
    title: string;
    subtitle: string;
    fixAction: string;
    pendingCount: string;
  };
}

const en: Translations = {
  nav: {
    overview: "Overview",
    onboarding: "Onboarding",
    myApplications: "My applications",
    review: "Document review",
    analytics: "Ops analytics",
    training: "Training & LMS",
    notifications: "Notifications",
    account: "Account & security",
    adminUsers: "Users",
    adminReviewers: "Reviewers",
    adminApplications: "Applications",
    adminRoles: "Roles & permissions",
    adminRules: "Business rules",
    adminIntegrations: "Integrations & LMS",
    adminAudit: "Audit log",
    adminSystem: "System status",
    signOut: "Sign out",
  },
  wizard: {
    title: "POSP Agent Onboarding",
    subtitle: "Complete your IRDAI Point of Sales Person registration in 6 guided steps",
    step0_badge: "Instant Pre-Flight Active",
    step1_title: "1. Personal Details",
    step2_title: "2. Address & State",
    step3_title: "3. Class 10 Education",
    step4_title: "4. Bank Mandate",
    step5_title: "5. Mandatory KYC Documents",
    step6_title: "6. Final Review & Submit",
    saveDraft: "Save draft",
    continue: "Continue",
    back: "Back",
    submit: "Submit application",
    submitting: "Submitting & evaluating...",
    saving: "Saving...",
    draftSaved: "Draft saved successfully.",
    fastTrack: "Fast-Track Auto-Fill Available",
    fastTrackNotice: "Upload your PAN Card first in Step 5 to automatically populate your name, DOB, and PAN number across the wizard.",
  },
  docs: {
    title: "Mandatory KYC Documents",
    subtitle: "Upload clear photos or PDFs. Sensitive Aadhaar numbers are automatically masked per DPDP Act 2023.",
    pan: "1. PAN Card",
    panDesc: "Clear color copy of your individual Permanent Account Number card.",
    aadhaarFront: "2. Aadhaar Front",
    aadhaarFrontDesc: "Front side showing your photograph, name, and birth year. 8 digits are auto-masked.",
    aadhaarBack: "3. Aadhaar Back",
    aadhaarBackDesc: "Back side showing your permanent residential address and pincode.",
    marksheet: "4. Class 10 Marksheet",
    marksheetDesc: "Secondary school passing certificate or marks statement (minimum Class 10 pass).",
    cheque: "5. Cancelled Cheque / Bank Proof",
    chequeDesc: "Personal bank cheque showing printed name & IFSC code. Joint accounts must list you as primary.",
    selfie: "6. Applicant Selfie",
    selfieDesc: "Front-facing photograph with clear lighting, without sunglasses or caps.",
    uploadButton: "Upload file",
    reuploadButton: "Replace file",
    previewButton: "Preview",
    removeButton: "Remove",
    cameraButton: "Take with camera",
    guidedButton: "Guided capture & auto-rotate",
    qualityOk: "Quality verified",
    qualityIssue: "Quality defect detected",
    dpdpNotice: "Digital Personal Data Protection (DPDP) Act 2023 Compliance",
    dpdpClause: "Your uploaded documents are processed securely in India. 12-digit Aadhaar numbers are automatically masked (first 8 digits obscured) in compliance with UIDAI regulations. Information is used solely for IRDAI POSP certification.",
    autofillApplied: "Document-first auto-fill applied to form fields.",
    uploadStage1: "1/4 Encrypting & applying DPDP 8-digit Aadhaar redaction...",
    uploadStage2: "2/4 Scanning edge quality (blur, glare, cropping)...",
    uploadStage3: "3/4 Gemini 3.5 Flash-Lite & local OCR extraction...",
    uploadStage4: "4/4 Adjudicating IRDAI Rulebook v3.2 consistency...",
  },
  camera: {
    title: "Live Camera Capture & Liveness Verification",
    close: "Close camera",
    takePhoto: "Capture photo",
    ready: "Position face in oval",
    centerFace: "Center your face in the oval guide",
    blinkPrompt: "Please blink your eyes or tilt head slightly to confirm liveness",
    livenessVerified: "Liveness & Lighting Verified",
    darkAlert: "Lighting is too dark. Move to a brighter area.",
    glareAlert: "Too much glare or direct light. Adjust your angle.",
    activePrompt: "Live motion detected. Ready to capture.",
  },
  rework: {
    title: "Action Required: Rework Requested",
    subtitle: "Our autonomous review detected document defects. Please upload the corrected documents below in one pass.",
    fixAction: "Upload fix",
    pendingCount: "items to correct",
  },
};

const hi: Translations = {
  nav: {
    overview: "अवलोकन (Overview)",
    onboarding: "ऑनबोर्डिंग (Onboarding)",
    myApplications: "मेरे आवेदन (My Applications)",
    review: "दस्तावेज़ समीक्षा (Review)",
    analytics: "ऑप्स एनालिटिक्स (Analytics)",
    training: "प्रशिक्षण एवं एलएमएस (LMS)",
    notifications: "सूचनाएं (Notifications)",
    account: "खाता एवं सुरक्षा (Account)",
    adminUsers: "उपयोगकर्ता (Users)",
    adminReviewers: "समीक्षक (Reviewers)",
    adminApplications: "सभी आवेदन (Applications)",
    adminRoles: "भूमिकाएं एवं अनुमतियां (Roles)",
    adminRules: "व्यापार नियम (Rules)",
    adminIntegrations: "एकीकरण (Integrations)",
    adminAudit: "ऑडिट लॉग (Audit Log)",
    adminSystem: "सिस्टम स्थिति (System)",
    signOut: "साइन आउट (Sign out)",
  },
  wizard: {
    title: "पीओएसपी एजेंट ऑनबोर्डिंग",
    subtitle: "6 सरल चरणों में अपना आईआरडीएआई (IRDAI) बीमा एजेंट पंजीकरण पूरा करें",
    step0_badge: "त्वरित पात्रता जांच सक्रिय",
    step1_title: "1. व्यक्तिगत विवरण",
    step2_title: "2. आवासीय पता एवं राज्य",
    step3_title: "3. 10वीं कक्षा की योग्यता",
    step4_title: "4. बैंक खाता विवरण",
    step5_title: "5. अनिवार्य केवाईसी दस्तावेज़",
    step6_title: "6. समीक्षा एवं अंतिम जमा",
    saveDraft: "ड्राफ्ट सहेजें",
    continue: "आगे बढ़ें",
    back: "पीछे जाएं",
    submit: "आवेदन जमा करें",
    submitting: "जमा एवं मूल्यांकन हो रहा है...",
    saving: "सहेजा जा रहा है...",
    draftSaved: "ड्राफ्ट सफलतापूर्वक सहेज लिया गया।",
    fastTrack: "दस्तावेज़-आधारित ऑटो-फिल उपलब्ध",
    fastTrackNotice: "चरण 5 में पहले अपना पैन कार्ड अपलोड करें ताकि आपका नाम, जन्मतिथि और पैन नंबर पूरे फॉर्म में अपने-आप भर जाएं।",
  },
  docs: {
    title: "अनिवार्य केवाईसी दस्तावेज़",
    subtitle: "स्पष्ट फोटो या पीडीएफ अपलोड करें। डीपीमडीपी (DPDP) अधिनियम 2023 के तहत आधार नंबर स्वतः छिपा दिया जाता है।",
    pan: "1. पैन कार्ड (PAN Card)",
    panDesc: "अपने व्यक्तिगत पैन कार्ड की स्पष्ट रंगीन प्रति अपलोड करें।",
    aadhaarFront: "2. आधार कार्ड सामने का भाग (Aadhaar Front)",
    aadhaarFrontDesc: "सामने का भाग जिसमें फोटो, नाम और जन्म वर्ष दिखाई दे। पहले 8 अंक स्वतः मास्क हो जाते हैं।",
    aadhaarBack: "3. आधार कार्ड पीछे का भाग (Aadhaar Back)",
    aadhaarBackDesc: "पीछे का भाग जिसमें आपका स्थायी आवासीय पता और पिनकोड स्पष्ट दिखाई दे।",
    marksheet: "4. 10वीं कक्षा की अंकतालिका (Marksheet)",
    marksheetDesc: "माध्यमिक विद्यालय उत्तीर्ण प्रमाण पत्र या अंकतालिका (न्यूनतम 10वीं पास आवश्यक)।",
    cheque: "5. रद्द चेक या पासबुक (Cheque / Passbook)",
    chequeDesc: "व्यक्तिगत बैंक चेक जिसमें मुद्रित नाम और आईएफएससी (IFSC) कोड दिखे। संयुक्त खाते में आपका मुख्य धारक होना जरूरी है।",
    selfie: "6. लाइव सेल्फी (Live Selfie)",
    selfieDesc: "सीधी सामने की सेल्फी, साफ रोशनी में, बिना चश्मे या टोपी के।",
    uploadButton: "फ़ाइल अपलोड करें",
    reuploadButton: "फ़ाइल बदलें",
    previewButton: "पूर्वावलोकन",
    removeButton: "हटाएं",
    cameraButton: "कैमरे से फोटो लें",
    guidedButton: "गाइडेड कैप्चर और ऑटो-रोटेट",
    qualityOk: "गुणवत्ता सत्यापित (OK)",
    qualityIssue: "गुणवत्ता में खामी मिली",
    dpdpNotice: "डिजिटल व्यक्तिगत डेटा संरक्षण (DPDP) अधिनियम 2023 अनुपालन",
    dpdpClause: "आपके द्वारा अपलोड किए गए दस्तावेज़ भारत में सुरक्षित रूप से संसाधित होते हैं। यूआईडीएआई (UIDAI) नियमों के अनुसार 12-अंकीय आधार नंबर के पहले 8 अंक स्वतः छिपा दिए जाते हैं। जानकारी का उपयोग केवल आईआरडीएआई (IRDAI) एजेंट प्रमाणीकरण के लिए किया जाता है।",
    autofillApplied: "दस्तावेज़ से डेटा स्वतः फॉर्म में भर दिया गया है।",
    uploadStage1: "1/4 एन्क्रिप्शन एवं आधार 8-अंक रिडक्शन लागू किया जा रहा है...",
    uploadStage2: "2/4 छवि गुणवत्ता (धुंधलापन, चमक, क्रॉप) की जांच जारी है...",
    uploadStage3: "3/4 जेमिनी 3.5 फ्लैश-लाइट एवं ओसीआर द्वारा टेक्स्ट निकाला जा रहा है...",
    uploadStage4: "4/4 आईआरडीएआई नियमपुस्तिका v3.2 से मिलान किया जा रहा है...",
  },
  camera: {
    title: "लाइव कैमरा कैप्चर एवं सजीवता (Liveness) सत्यापन",
    close: "कैमरा बंद करें",
    takePhoto: "फोटो खींचें",
    ready: "चेहरे को अंडाकार गाइड में रखें",
    centerFace: "अपने चेहरे को अंडाकार फ्रेम के केंद्र में रखें",
    blinkPrompt: "कृपया सजीवता सत्यापित करने के लिए पलकें झपकाएं या सिर थोड़ा घुमाएं",
    livenessVerified: "सजीवता एवं रोशनी सत्यापित (Verified)",
    darkAlert: "रोशनी बहुत कम है। कृपया अधिक रोशनी वाले स्थान पर जाएं।",
    glareAlert: "अत्यधिक चमक या सीधी रोशनी है। कृपया कोण बदलें।",
    activePrompt: "सजीव गति का पता चला। फोटो लेने के लिए तैयार।",
  },
  rework: {
    title: "आवश्यक कार्रवाई: दस्तावेज़ सुधार अनुरोध",
    subtitle: "हमारी स्वचालित समीक्षा ने दस्तावेज़ में खामियां पाई हैं। कृपया नीचे दिए गए सही दस्तावेज़ एक बार में अपलोड करें।",
    fixAction: "सुधार अपलोड करें",
    pendingCount: "दस्तावेज़ ठीक करने हैं",
  },
};

interface I18nContextType {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: Translations;
}

const I18nContext = createContext<I18nContextType>({
  locale: "en",
  setLocale: () => {},
  t: en,
});

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");

  useEffect(() => {
    try {
      const saved = localStorage.getItem("policynest_locale") as Locale | null;
      if (saved === "en" || saved === "hi") {
        setLocaleState(saved);
      }
    } catch {
      // ignore localStorage restrictions
    }
  }, []);

  const setLocale = (newLocale: Locale) => {
    setLocaleState(newLocale);
    try {
      localStorage.setItem("policynest_locale", newLocale);
    } catch {
      // ignore
    }
  };

  const t = locale === "hi" ? hi : en;

  return (
    <I18nContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  return useContext(I18nContext);
}
