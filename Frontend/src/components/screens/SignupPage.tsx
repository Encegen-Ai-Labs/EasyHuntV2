"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSignupMutation } from "@/services/api/hooks";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { CheckCircle2 } from "lucide-react";

export function SignupPage() {
  const router = useRouter();
  const signupMutation = useSignupMutation();

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    const payload = {
      name: String(formData.get("name") ?? ""),
      email: String(formData.get("email") ?? ""),
      password: String(formData.get("password") ?? ""),
      confirmPassword: String(formData.get("password") ?? ""),
      phone: "",
    };
    const result = await signupMutation.mutateAsync(payload);
    if (result.success) {
      router.push("/login");
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto grid max-w-6xl overflow-hidden py-10 px-4 lg:grid-cols-[1fr_0.95fr]">
        <div className="overflow-hidden rounded-2xl lg:grid lg:grid-cols-[1fr_0.95fr]" style={{ display: "contents" }}>
          {/* Left panel */}
          <section className="rounded-l-2xl bg-primary p-10 text-primary-foreground">
            <div className="flex items-center gap-3">
              <span className="flex size-11 items-center justify-center rounded-xl bg-primary-foreground/10 ring-1 ring-primary-foreground/20">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                  <path d="M5 12h14M12 5l7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-widest opacity-60">PropVerify AI</div>
                <div className="text-xl font-semibold">Workspace Onboarding</div>
              </div>
            </div>

            <div className="mt-14">
              <h1 className="max-w-md text-3xl font-bold leading-tight tracking-tight">
                Create your case intelligence workspace
              </h1>
              <p className="mt-4 max-w-sm text-sm leading-relaxed opacity-70">
                Organize legal, financial, title, and parcel intelligence into a single review-ready operating layer.
              </p>
            </div>

            <div className="mt-10 flex flex-col gap-3">
              {["Document ingestion", "Risk review workflows", "Executive reporting"].map((item) => (
                <div key={item} className="flex items-center gap-3">
                  <CheckCircle2 size={16} className="opacity-80" />
                  <span className="text-sm font-medium">{item}</span>
                </div>
              ))}
            </div>
          </section>

          {/* Right panel */}
          <section className="rounded-r-2xl border border-border bg-card p-8 md:p-12">
            <div className="mb-7">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Create account</p>
              <h2 className="mt-2 text-2xl font-bold tracking-tight">Set up PropVerify</h2>
            </div>

            <form className="flex flex-col gap-4" onSubmit={onSubmit}>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="signup-name" className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Full name
                </label>
                <Input id="signup-name" name="name" placeholder="Alex Carter" />
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="signup-email" className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Work email
                </label>
                <Input id="signup-email" name="email" type="email" placeholder="alex@company.com" />
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="signup-password" className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Password
                </label>
                <Input id="signup-password" name="password" type="password" placeholder="••••••••" />
              </div>
              <Button type="submit" className="w-full" disabled={signupMutation.isPending}>
                {signupMutation.isPending ? "Creating workspace…" : "Create workspace"}
              </Button>
            </form>

            <div className="my-5 flex items-center gap-3">
              <Separator className="flex-1" />
              <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">or</span>
              <Separator className="flex-1" />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Button variant="outline" className="w-full">Google</Button>
              <Button variant="outline" className="w-full">Microsoft</Button>
            </div>

            <p className="mt-7 text-center text-sm text-muted-foreground">
              Already have an account?{" "}
              <Link href="/login" className="font-semibold hover:underline">Sign in</Link>
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
