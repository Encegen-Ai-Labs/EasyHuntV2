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

const MOCK_CASES: CaseResponse[] = [
  {
    id: "case-1",
    vendor_id: "mock-vendor",
    reviewer_id: null,
    property_address: "12 MG Road, Bengaluru",
    survey_number: "SY-101/2A",
    status: "open",
    created_at: "2026-07-01T09:15:00.000Z",
    updated_at: "2026-07-01T09:15:00.000Z",
  },
  {
    id: "case-2",
    vendor_id: "mock-vendor",
    reviewer_id: "mock-reviewer",
    property_address: "45 Anna Salai, Chennai",
    survey_number: "SY-77/3",
    status: "processing",
    created_at: "2026-07-05T13:40:00.000Z",
    updated_at: "2026-07-06T10:00:00.000Z",
  },
  {
    id: "case-3",
    vendor_id: "mock-vendor",
    reviewer_id: "mock-reviewer",
    property_address: "8 Marine Drive, Mumbai",
    survey_number: "SY-19/1B",
    status: "review",
    created_at: "2026-07-10T08:00:00.000Z",
    updated_at: "2026-07-12T16:20:00.000Z",
  },
  {
    id: "case-4",
    vendor_id: "mock-vendor",
    reviewer_id: "mock-reviewer",
    property_address: "3 Park Street, Kolkata",
    survey_number: "SY-52/4",
    status: "completed",
    created_at: "2026-06-20T11:30:00.000Z",
    updated_at: "2026-06-25T09:00:00.000Z",
  },
];

// Mock. Swap the body for a real call once the API is reachable:
//   GET {API_BASE}/api/v1/cases  with Authorization: Bearer <token>
export async function listCases() {
  await new Promise((r) => setTimeout(r, 500));
  return {
    success: true,
    cases: MOCK_CASES,
  };
}

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
