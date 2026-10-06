const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type ReviewerPayload = {
  email: string;
  password: string;
  organisation_name: string;
};

export async function createReviewer(payload: ReviewerPayload, token: string) {
  const response = await fetch(`${API_BASE}/api/v1/admin/reviewers`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail ?? "Could not create reviewer account");
  }

  return body as {
    user_id: string;
    email: string;
    role: "Reviewer";
    password: string;
  };
}
