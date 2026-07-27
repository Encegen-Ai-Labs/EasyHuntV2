"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listCases, CaseResponse } from "@/lib/cases";

const STATUS_STYLES: Record<CaseResponse["status"], string> = {
  open: "bg-blue-50 text-blue-700 border-blue-200",
  processing: "bg-amber-50 text-amber-700 border-amber-200",
  review: "bg-purple-50 text-purple-700 border-purple-200",
  completed: "bg-green-50 text-green-700 border-green-200",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function CasesPage() {
  const [cases, setCases] = useState<CaseResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const result = await listCases();
      setLoading(false);
      if (result.success) {
        setCases(result.cases);
      }
    }
    load();
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-8">
      <div className="w-full max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">Cases</h1>
            <p className="text-sm text-gray-500">
              Property due diligence cases
            </p>
          </div>
          <Link
            href="/cases/new"
            className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 text-sm font-medium"
          >
            New case
          </Link>
        </div>

        <div className="bg-white rounded-lg shadow">
          {loading && (
            <p className="p-6 text-sm text-gray-500">Loading cases...</p>
          )}

          {!loading && cases.length === 0 && (
            <p className="p-6 text-sm text-gray-500">
              No cases yet.{" "}
              <Link href="/cases/new" className="text-blue-600 hover:underline">
                Create your first case
              </Link>
              .
            </p>
          )}

          {!loading && cases.length > 0 && (
            <ul className="divide-y divide-gray-100">
              {cases.map((c) => (
                <li key={c.id}>
                  <Link
                    href={`/cases/${c.id}`}
                    className="flex items-center justify-between p-4 hover:bg-gray-50"
                  >
                    <div>
                      <p className="font-medium text-gray-900">
                        {c.property_address}
                      </p>
                      <p className="text-sm text-gray-500">
                        Survey no. {c.survey_number} &middot;{" "}
                        {formatDate(c.created_at)}
                      </p>
                    </div>
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full border text-xs font-medium capitalize ${STATUS_STYLES[c.status]}`}
                    >
                      {c.status}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
