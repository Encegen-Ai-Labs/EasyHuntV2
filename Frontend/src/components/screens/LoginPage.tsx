"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, CheckCircle2, FileCheck2, ShieldCheck, Unlock } from "lucide-react";
import { useLoginMutation } from "@/services/api/hooks";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

export function LoginPage() {
  const router = useRouter();
  const loginMutation = useLoginMutation();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(loginSchema), defaultValues: { email: "", password: "" } });

  async function onSubmit(data: any) {
    const result = await loginMutation.mutateAsync({ email: data.email, password: data.password });
    if (result.success) {
      router.push("/dashboard");
    } else {
      console.error(result.error);
    }
  }

  return (
    <div className="min-h-screen">
      <div className="grid min-h-screen lg:grid-cols-[1.1fr_0.9fr]">
        {/* Left panel */}
        <section className="relative flex flex-col justify-between overflow-hidden bg-primary p-10 text-primary-foreground">
          <div className="relative z-10 flex items-center gap-3">
            <span className="flex size-10 items-center justify-center rounded-xl bg-primary-foreground/10 ring-1 ring-primary-foreground/20">
              <FileCheck2 size={20} />
            </span>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-widest opacity-60">PropVerify AI</div>
              <div className="text-lg font-semibold leading-none">Risk Intelligence</div>
            </div>
          </div>

          <div className="relative z-10 max-w-xl">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary-foreground/20 bg-primary-foreground/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-widest opacity-80">
              <span className="size-1.5 rounded-full bg-primary-foreground" />
              Property Intelligence Console
            </div>
            <h1 className="text-4xl font-bold leading-tight tracking-tight lg:text-5xl">
              Turn property documents into verified decisions.
            </h1>
            <p className="mt-5 max-w-md text-base leading-relaxed opacity-70">
              Automate extraction, triage review, monitor encumbrances, and generate risk-ready evidence from intake to report.
            </p>

            <div className="mt-8 flex flex-col gap-3">
              {[
                { icon: ShieldCheck, label: "OCR + title intelligence", detail: "Map property records to signed-field extraction" },
                { icon: CheckCircle2, label: "Risk-aware workflow", detail: "Prioritize liens, judgments, title and value review" },
                { icon: Unlock, label: "Secure review events", detail: "Maintain editable audit-ready source-of-truth" },
              ].map(({ icon: Icon, label, detail }) => (
                <div key={label} className="flex items-center gap-3">
                  <span className="flex size-9 items-center justify-center rounded-lg bg-primary-foreground/10 ring-1 ring-primary-foreground/20">
                    <Icon size={16} />
                  </span>
                  <div>
                    <div className="text-sm font-semibold">{label}</div>
                    <div className="text-xs opacity-60">{detail}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="relative z-10 flex items-center gap-8 text-sm opacity-60">
            <span className="font-medium">24k+ records</span>
            <span className="font-medium">99.9% uptime</span>
            <span className="font-medium">SOC 2 ready</span>
          </div>
        </section>

        {/* Right panel */}
        <section className="flex items-center justify-center bg-background px-6 py-12">
          <div className="w-full max-w-md">
            <div className="mb-6">
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Welcome back</p>
              <h2 className="mt-2 text-2xl font-bold tracking-tight">Sign in</h2>
              <p className="mt-1 text-sm text-muted-foreground">Access the PropVerify intelligence workspace</p>
            </div>

            <Card>
              <CardContent className="pt-6">
                <form className="flex flex-col gap-4" onSubmit={handleSubmit(onSubmit)}>
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="login-email" className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                      Work email
                    </label>
                    <Input id="login-email" type="email" placeholder="alex@propverify.ai" {...register("email")} aria-invalid={!!errors.email} />
                    {errors.email && <p className="text-xs text-destructive">{String(errors.email.message)}</p>}
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="login-password" className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                      Password
                    </label>
                    <Input id="login-password" type="password" placeholder="••••••••" {...register("password")} aria-invalid={!!errors.password} />
                    {errors.password && <p className="text-xs text-destructive">{String(errors.password.message)}</p>}
                  </div>

                  <div className="flex items-center justify-between">
                    <label className="flex items-center gap-2 text-xs text-muted-foreground">
                      <input type="checkbox" className="rounded border-border" />
                      Keep me signed in
                    </label>
                    <a href="#" className="text-xs font-semibold hover:underline">Forgot password?</a>
                  </div>

                  <Button type="submit" className="w-full" disabled={isSubmitting}>
                    {isSubmitting ? "Signing in…" : "Continue to workspace"}
                    <ArrowRight data-icon="inline-end" />
                  </Button>
                </form>

                <div className="my-5 flex items-center gap-3">
                  <Separator className="flex-1" />
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">or continue with</span>
                  <Separator className="flex-1" />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <Button variant="outline" className="w-full">Google</Button>
                  <Button variant="outline" className="w-full">Microsoft</Button>
                </div>

                <p className="mt-5 text-center text-sm text-muted-foreground">
                  New to PropVerify AI?{" "}
                  <Link href="/signup" className="font-semibold hover:underline">Create account</Link>
                </p>
              </CardContent>
            </Card>
          </div>
        </section>
      </div>
    </div>
  );
}
