"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Input from "@/components/ui/Input";
import { createReviewer } from "@/lib/admin";

export default function AdminPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [form, setForm] = useState({ email: "", password: "", organisation_name: "" });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const role = localStorage.getItem("user_role");
    const storedToken = localStorage.getItem("access_token");
    if (role !== "Admin" || !storedToken) {
      router.replace("/login");
      return;
    }
    setToken(storedToken);
  }, [router]);

  function updateField(event: React.ChangeEvent<HTMLInputElement>) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    setError("");
    setLoading(true);
    try {
      const reviewer = await createReviewer(form, token);
      setMessage(`Reviewer created. Login ID: ${reviewer.email} | Password: ${reviewer.password}`);
      setForm({ email: "", password: "", organisation_name: "" });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not create reviewer account");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 px-4 py-10">
      <section className="mx-auto max-w-lg rounded-lg bg-white p-8 shadow">
        <h1 className="text-2xl font-bold">Create reviewer account</h1>
        <p className="mt-1 text-sm text-gray-500">Create credentials to share with the reviewer.</p>

        {message && <p className="mt-4 rounded-md bg-green-50 p-3 text-sm text-green-700">{message}</p>}
        {error && <p className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}

        <form onSubmit={handleSubmit} className="mt-6" noValidate>
          <Input label="Email / login ID" name="email" type="email" value={form.email} onChange={updateField} />
          <Input label="Temporary password" name="password" type="password" value={form.password} onChange={updateField} />
          <Input label="Organisation" name="organisation_name" value={form.organisation_name} onChange={updateField} />
          <button type="submit" disabled={loading || !token} className="w-full rounded-md bg-blue-600 py-2 text-white hover:bg-blue-700 disabled:opacity-50">
            {loading ? "Creating account..." : "Create reviewer"}
          </button>
        </form>
      </section>
    </main>
  );
}