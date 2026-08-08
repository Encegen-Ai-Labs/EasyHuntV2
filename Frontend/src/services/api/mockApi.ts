export type CaseStatus =
  | "Draft"
  | "Processing"
  | "Needs Review"
  | "Flagged"
  | "Completed";

export interface CaseRecord {
  id: string;
  title: string;
  address: string;
  propertyType: string;
  createdAt: string;
  priority: "Low" | "Normal" | "High" | "Critical";
  status: CaseStatus;
  assignee: {
    name: string;
    avatar: string;
  };
  risk: "Low" | "Medium" | "High" | "Critical";
  confidence: number;
}

export const dashboardCases: CaseRecord[] = [
  {
    id: "PV-2408",
    title: "1800 Meridian Avenue",
    address: "1800 Meridian Ave, Miami FL",
    propertyType: "Residential",
    createdAt: "2026-08-01",
    priority: "High",
    status: "Needs Review",
    assignee: { name: "Avery Johnson", avatar: "AJ" },
    risk: "Critical",
    confidence: 86,
  },
  {
    id: "PV-2407",
    title: "960 St. James Drive",
    address: "960 St. James Dr, Atlanta GA",
    propertyType: "Mixed Use",
    createdAt: "2026-07-28",
    priority: "Normal",
    status: "Flagged",
    assignee: { name: "Mia Rivera", avatar: "MR" },
    risk: "High",
    confidence: 78,
  },
  {
    id: "PV-2406",
    title: "Flagship Storage Holdings",
    address: "2101 Ellis Parkway, Dallas TX",
    propertyType: "Industrial",
    createdAt: "2026-07-26",
    priority: "Critical",
    status: "Completed",
    assignee: { name: "Liam Turner", avatar: "LT" },
    risk: "Low",
    confidence: 96,
  },
  {
    id: "PV-2405",
    title: "Crownview Retail Campus",
    address: "428 Westline Blvd, Charlotte NC",
    propertyType: "Retail",
    createdAt: "2026-07-24",
    priority: "Low",
    status: "Processing",
    assignee: { name: "Noah Carter", avatar: "NC" },
    risk: "Medium",
    confidence: 81,
  },
];

export async function getDashboardCases(): Promise<{ data: CaseRecord[] }> {
  await new Promise((resolve) => setTimeout(resolve, 350));
  return { data: dashboardCases };
}

export async function getCaseById(id: string): Promise<{ data: CaseRecord }> {
  await new Promise((resolve) => setTimeout(resolve, 250));
  const found = dashboardCases.find((caseItem) => caseItem.id === id) ?? dashboardCases[0];
  return { data: { ...found, id } };
}

export async function getExtractedFields(): Promise<any> {
  await new Promise((resolve) => setTimeout(resolve, 200));
  return {
    data: {
      title: "1800 Meridian Avenue",
      owner: "Meridian Holdings LLC",
      parcelId: "FL-01791-4826",
      propertyType: "Residential",
      fairMarketValue: "$845,000",
      taxAssessment: "$736,180",
      liabilities: "$36,240",
      encumbrances: "Lis pendens",
      fields: [
        {
          group: "Ownership & Title",
          fields: [
            { key: "Owner", value: "Meridian Holdings LLC", confidence: 98, id: "owner" },
            { key: "Title Status", value: "Clear", confidence: 92, id: "title-status" },
            { key: "Deed Type", value: "Warranty Deed", confidence: 88, id: "deed-type" },
          ],
        },
        {
          group: "Financials",
          fields: [
            { key: "Fair Market Value", value: "$845,000", confidence: 91, id: "market-value" },
            { key: "Tax Assessment", value: "$736,180", confidence: 83, id: "tax-assessment" },
            { key: "Mortgage Balance", value: "$417,500", confidence: 74, id: "mortgage" },
          ],
        },
        {
          group: "Encumbrances",
          fields: [
            { key: "Tax Lien", value: "None", confidence: 95, id: "tax-lien" },
            { key: "Open Judgment", value: "Monroe County", confidence: 68, id: "judgment" },
          ],
        },
      ],
    },
  };
}

export async function login(email: string, password: string) {
  await new Promise((r) => setTimeout(r, 500));
  if (password === "wrongpassword") {
    return { success: false, error: "Invalid login credentials" };
  }
  return { success: true, user: { id: "mock-1", email, name: "Mock User" } };
}

export type SignupData = {
  name: string;
  email: string;
  password: string;
  confirmPassword: string;
  phone: string;
};

export async function signup(data: SignupData) {
  await new Promise((r) => setTimeout(r, 500));
  return {
    success: true,
    user: { id: "mock-2", email: data.email, name: data.name },
  };
}
