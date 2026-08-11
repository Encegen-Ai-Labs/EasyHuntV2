import { CaseCreationPage } from "@/components/screens/CaseCreationPage";

export default function CaseNewRoute() {
  return <CaseCreationPage />;
"use client";

import { useState } from "react";
import Input from "@/components/ui/Input";
import { createCase } from "@/lib/cases";

export default function NewCasePage() {
  const [form, setForm] = useState({
    property_address: "",
    survey_number: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  }

  function validate(): Record<string, string> {
    const next: Record<string, string> = {};

    if (!form.property_address.trim()) {
      next.property_address = "Property address is required";
    }
    if (!form.survey_number.trim()) {
      next.survey_number = "Survey number is required";
    }

    return next;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    setLoading(true);
    const result = await createCase(form);
    setLoading(false);

    if (!result.success) {
      setErrors({ form: "Could not create case" });
      return;
    }

    console.log("Case created:", result.case);
    // router.push("/cases");  // enable once the case list exists
  }

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-8">
      <div className="w-full max-w-2xl mx-auto bg-white p-8 rounded-lg shadow">
        <h1 className="text-2xl font-bold mb-1">New property case</h1>
        <p className="text-sm text-gray-500 mb-6">
          Create a case to begin document verification
        </p>

        {errors.form && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
            {errors.form}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <Input
            label="Property address"
            name="property_address"
            value={form.property_address}
            onChange={handleChange}
            error={errors.property_address}
          />
          <Input
            label="Survey number"
            name="survey_number"
            value={form.survey_number}
            onChange={handleChange}
            error={errors.survey_number}
          />

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Creating case..." : "Create case"}
          </button>
        </form>
      </div>
    </div>
  );
}
