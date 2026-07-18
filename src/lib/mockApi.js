// Mock auth layer.
// Shaped to match Supabase Auth so wiring is a one-file change:
//   login  -> supabase.auth.signInWithPassword({ email, password })
//   signup -> supabase.auth.signUp({ email, password, options: { data: {...} } })

export async function login(email, password) {
  await new Promise((r) => setTimeout(r, 500));
  if (password === "wrongpassword") {
    return { success: false, error: "Invalid login credentials" };
  }
  return { success: true, user: { id: "mock-1", email, name: "Mock User" } };
}

export async function signup(data) {
  await new Promise((r) => setTimeout(r, 500));
  return {
    success: true,
    user: { id: "mock-2", email: data.email, name: data.name },
  };
}