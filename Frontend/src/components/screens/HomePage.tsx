"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/AuthContext";

const STEPS = [
  { name: "Upload", line: "Add the property documents. Handwritten and typed pages are read for you." },
  { name: "Review and approve", line: "Check each document against its extracted details. Approve it, or undo later." },
  { name: "Search and select", line: "Find a name or number, tick the spellings you mean, pick the text to quote." },
  { name: "Report", line: "A title search report or one of nine bank formats. Edit it, then download Word or PDF." },
];

const PROMISES = [
  "Only documents you approve are searched or used in a report.",
  "Opinion, marketability and adverse remarks are never filled in for you.",
  "Every value taken from a document is marked so you can check it.",
];

export function HomePage() {
  const { isAuthenticated, isLoading } = useAuth();
  const signedIn = !isLoading && isAuthenticated;

  return (
    <main className="mx-auto max-w-5xl px-6 pb-24 pt-16 md:pt-24">
      <section className="grid gap-12 md:grid-cols-[1.1fr_1fr] md:gap-16">
        <div>
          <h1 className="font-heading text-4xl font-medium leading-[1.1] tracking-tight md:text-6xl">
            Title scrutiny, checked by you.
          </h1>
          <p className="mt-6 max-w-md text-lg leading-relaxed text-muted-foreground">
            EasyHunt reads the property documents and fills what they state. You decide what is right and what goes in the
            report.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3">
            <Button size="lg" className="h-11 px-6" nativeButton={false} render={<Link href={signedIn ? "/cases" : "/login"} />}>
              {signedIn ? "Open your cases" : "Sign in"}
              <ArrowRight className="ml-2 size-4" />
            </Button>
            {signedIn && (
              <Link href="/cases/new" className="text-sm font-medium underline underline-offset-4 hover:text-primary">
                Start a new case
              </Link>
            )}
          </div>
        </div>

        <ol className="divide-y divide-border border-y border-border">
          {STEPS.map((step, index) => (
            <li key={step.name} className="grid grid-cols-[2rem_1fr] gap-x-3 py-5">
              <span className="font-heading text-2xl leading-none text-primary">{index + 1}</span>
              <div>
                <p className="font-semibold">{step.name}</p>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{step.line}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="mt-20 border-t border-border pt-8 md:mt-28">
        <ul className="grid gap-6 md:grid-cols-3 md:gap-10">
          {PROMISES.map((promise) => (
            <li key={promise} className="text-base leading-relaxed">
              {promise}
            </li>
          ))}
        </ul>
      </section>

      <footer className="mt-24 text-sm text-muted-foreground">Encegen AI Labs</footer>
    </main>
  );
}
