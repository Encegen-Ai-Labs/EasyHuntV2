export type CaseCreate = {
  property_address: string;
  survey_number: string;
};

export type CaseResponse = {
  id: string;
  vendor_id: string;
  reviewer_id: string | null;
  property_address: string;
  survey_number: string;
  status: "open" | "processing" | "review" | "completed";
  created_at: string;
  updated_at: string;
};

// Mock. Swap the body for a real call once the API is reachable:
//   POST {API_BASE}/api/v1/cases  with Authorization: Bearer <token>
//   Requires role Vendor or Admin.
export async function createCase(payload: CaseCreate) {
  await new Promise((r) => setTimeout(r, 500));
  const now = new Date().toISOString();
  return {
    success: true,
    case: {
      id: "case-" + Date.now(),
      vendor_id: "mock-vendor",
      reviewer_id: null,
      property_address: payload.property_address,
      survey_number: payload.survey_number,
      status: "open",
      created_at: now,
      updated_at: now,
    } as CaseResponse,
  };
}
