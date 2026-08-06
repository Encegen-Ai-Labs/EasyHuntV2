export async function login(email: string, password: string) {
  await new Promise((r) => setTimeout(r, 500));
  if (password === "wrongpassword") {
    return { success: false, error: "Invalid login credentials" };
  }
  return { success: true, user: { id: "mock-1", email, name: "Mock User" } };
}

type SignupData = {
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