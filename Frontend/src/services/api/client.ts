import {
  getCaseById,
  getDashboardCases,
  getExtractedFields,
  login,
  signup,
  type SignupData,
} from "@/services/api/mockApi";

export const apiClient = {
  dashboard: {
    getCases: async () => getDashboardCases(),
  },
  cases: {
    getById: async (id: string) => getCaseById(id),
    getExtractedFields: async () => getExtractedFields(),
  },
  auth: {
    login: async (email: string, password: string) => login(email, password),
    signup: async (payload: SignupData) => signup(payload),
  },
};
