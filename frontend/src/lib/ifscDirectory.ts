/**
 * Offline Indian Bank IFSC Code Directory.
 * Matches the first 4 characters of an Indian IFSC code to its official bank entity.
 * Provides instant zero-latency feedback as candidates type, with zero external network dependency.
 */

export interface OfflineBankMatch {
  bankCode: string;
  bankName: string;
  category: "PUBLIC" | "PRIVATE" | "PAYMENTS" | "SMALL_FINANCE" | "FOREIGN" | "COOPERATIVE";
}

export const OFFLINE_IFSC_BANKS: Record<string, { name: string; category: OfflineBankMatch["category"] }> = {
  // Public Sector Banks
  SBIN: { name: "State Bank of India", category: "PUBLIC" },
  PUNB: { name: "Punjab National Bank", category: "PUBLIC" },
  BARB: { name: "Bank of Baroda", category: "PUBLIC" },
  CANR: { name: "Canara Bank", category: "PUBLIC" },
  UBIN: { name: "Union Bank of India", category: "PUBLIC" },
  IDIB: { name: "Indian Bank", category: "PUBLIC" },
  IOBA: { name: "Indian Overseas Bank", category: "PUBLIC" },
  CBIN: { name: "Central Bank of India", category: "PUBLIC" },
  MAHB: { name: "Bank of Maharashtra", category: "PUBLIC" },
  BKID: { name: "Bank of India", category: "PUBLIC" },
  PSIB: { name: "Punjab & Sind Bank", category: "PUBLIC" },
  UCBA: { name: "UCO Bank", category: "PUBLIC" },

  // Major Private Banks
  HDFC: { name: "HDFC Bank", category: "PRIVATE" },
  ICIC: { name: "ICICI Bank", category: "PRIVATE" },
  AXIS: { name: "Axis Bank", category: "PRIVATE" },
  UTIB: { name: "Axis Bank", category: "PRIVATE" },
  KKBK: { name: "Kotak Mahindra Bank", category: "PRIVATE" },
  YESB: { name: "Yes Bank", category: "PRIVATE" },
  IDFB: { name: "IDFC First Bank", category: "PRIVATE" },
  INDB: { name: "IndusInd Bank", category: "PRIVATE" },
  FED: { name: "Federal Bank", category: "PRIVATE" },
  FDRL: { name: "Federal Bank", category: "PRIVATE" },
  KVBL: { name: "Karur Vysya Bank", category: "PRIVATE" },
  SIBL: { name: "South Indian Bank", category: "PRIVATE" },
  RATN: { name: "RBL Bank", category: "PRIVATE" },
  BAND: { name: "Bandhan Bank", category: "PRIVATE" },
  CSBK: { name: "CSB Bank", category: "PRIVATE" },
  DCBL: { name: "DCB Bank", category: "PRIVATE" },
  DLXB: { name: "Dhanlaxmi Bank", category: "PRIVATE" },
  TMBL: { name: "Tamilnad Mercantile Bank", category: "PRIVATE" },
  JAKA: { name: "Jammu & Kashmir Bank", category: "PRIVATE" },
  KBLA: { name: "Karnataka Bank", category: "PRIVATE" },
  CIUB: { name: "City Union Bank", category: "PRIVATE" },
  NAVE: { name: "Nainital Bank", category: "PRIVATE" },

  // Small Finance Banks
  AUBL: { name: "AU Small Finance Bank", category: "SMALL_FINANCE" },
  ESFB: { name: "Equitas Small Finance Bank", category: "SMALL_FINANCE" },
  JSFB: { name: "Jana Small Finance Bank", category: "SMALL_FINANCE" },
  USFB: { name: "Ujjivan Small Finance Bank", category: "SMALL_FINANCE" },
  UTKS: { name: "Utkarsh Small Finance Bank", category: "SMALL_FINANCE" },
  NESF: { name: "North East Small Finance Bank", category: "SMALL_FINANCE" },
  SURY: { name: "Suryoday Small Finance Bank", category: "SMALL_FINANCE" },
  CSFB: { name: "Capital Small Finance Bank", category: "SMALL_FINANCE" },
  FSFB: { name: "Fincare Small Finance Bank", category: "SMALL_FINANCE" },
  SSFB: { name: "Shivalik Small Finance Bank", category: "SMALL_FINANCE" },
  USBL: { name: "Unity Small Finance Bank", category: "SMALL_FINANCE" },

  // Payments Banks
  IPOS: { name: "India Post Payments Bank", category: "PAYMENTS" },
  APBL: { name: "Airtel Payments Bank", category: "PAYMENTS" },
  PYTM: { name: "Paytm Payments Bank", category: "PAYMENTS" },
  JIOB: { name: "Jio Payments Bank", category: "PAYMENTS" },
  FINO: { name: "Fino Payments Bank", category: "PAYMENTS" },

  // Foreign Banks in India
  DBSS: { name: "DBS Bank India", category: "FOREIGN" },
  SCBL: { name: "Standard Chartered Bank", category: "FOREIGN" },
  CITI: { name: "Citibank India", category: "FOREIGN" },
  HSBC: { name: "HSBC Bank India", category: "FOREIGN" },
  BNPA: { name: "BNP Paribas India", category: "FOREIGN" },
  BARC: { name: "Barclays Bank", category: "FOREIGN" },

  // Major Scheduled Urban Co-operative Banks
  SVCB: { name: "SVC Co-operative Bank", category: "COOPERATIVE" },
  SRCB: { name: "Saraswat Co-operative Bank", category: "COOPERATIVE" },
  COSB: { name: "Cosmos Co-operative Bank", category: "COOPERATIVE" },
  NKGS: { name: "NKGSB Co-operative Bank", category: "COOPERATIVE" },
  TBSA: { name: "Thane Bharat Sahakari Bank", category: "COOPERATIVE" },
  ABHY: { name: "Abhyudaya Co-operative Bank", category: "COOPERATIVE" },
  GBCB: { name: "Greater Bombay Co-operative Bank", category: "COOPERATIVE" },
};

export function lookupOfflineIfsc(rawCode: string): OfflineBankMatch | null {
  const code = (rawCode || "").toUpperCase().trim();
  if (code.length < 4) return null;
  const prefix = code.slice(0, 4);
  const match = OFFLINE_IFSC_BANKS[prefix];
  if (match) {
    return {
      bankCode: prefix,
      bankName: match.name,
      category: match.category,
    };
  }
  return null;
}
