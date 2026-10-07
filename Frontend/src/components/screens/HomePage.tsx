import Link from "next/link";
import Image from "next/image";
import { ArrowRight, FileSearch, ShieldCheck, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

export function HomePage() {
  return (
    <div className="relative min-h-screen bg-background overflow-hidden selection:bg-indigo-500/30">
      
      {/* Background Ambient Glows */}
      <div className="absolute top-0 left-1/2 -z-10 h-[800px] w-[1000px] -translate-x-1/2 -translate-y-1/2 opacity-30 blur-[120px]">
        <div className="absolute inset-0 bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-500 rounded-full mix-blend-screen animate-pulse duration-[8000ms]" />
      </div>
      
      {/* Subtle Grid Pattern */}
      <div className="absolute inset-0 -z-20 h-full w-full bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)]"></div>

      {/* Hero */}
      <section className="relative px-6 pt-20 pb-16 lg:pt-28 lg:pb-24">
        <div className="mx-auto grid max-w-7xl grid-cols-1 items-center gap-12 lg:grid-cols-2 lg:gap-16">
          
          {/* Copy Content */}
          <div className="relative z-10 flex flex-col">
            <div className="inline-flex w-fit items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
              <span className="size-1.5 rounded-full bg-primary" />
              EasyHuntV2
            </div>
            
            <h1 className="mt-6 max-w-2xl text-4xl font-bold tracking-tight leading-tight text-foreground md:text-5xl">
              Property document review, with the source in view.
            </h1>
            
            <p className="mt-5 max-w-xl text-base leading-7 text-muted-foreground md:text-lg">
              Bring a case&apos;s property records together, review extracted details against page text, and prepare a report with the lawyer in control.
            </p>
            
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Button size="lg" className="h-11 px-6" nativeButton={false} render={<Link href="/cases/new" />}>
                Create a case
                <ArrowRight className="ml-2 size-4" />
              </Button>
              <Button variant="outline" size="lg" className="h-11 px-6" nativeButton={false} render={<Link href="/dashboard" />}>
                Open dashboard
              </Button>
            </div>
          </div>

          <div className="relative z-10 w-full lg:pl-4">
            <div className="overflow-hidden rounded-2xl border border-border bg-card p-2 shadow-xl">
              <div className="overflow-hidden rounded-xl">
                <Image 
                  src="/images/hero_abstract.png" 
                  alt="Illustration of property documents and review data"
                  width={600} 
                  height={500}
                  className="h-auto w-full object-cover"
                  priority
                />
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* Features Bento Grid */}
      <section id="platform" className="relative mx-auto max-w-7xl px-6 py-24">
        <div className="mb-16 max-w-2xl">
          <h2 className="text-3xl font-bold tracking-tight text-foreground md:text-4xl">One workspace for every review</h2>
          <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground md:text-lg">
            Upload related records, inspect machine-assisted extraction, and keep review and report work connected to the source documents.
          </p>
        </div>
        
        <div className="grid gap-6 md:grid-cols-3">
          <div className="group rounded-2xl border border-border bg-card p-7 transition-colors hover:bg-muted/40 md:col-span-2">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-400 ring-1 ring-indigo-500/20 transition-transform group-hover:scale-110">
              <FileSearch size={28} />
            </div>
            <h3 className="mt-5 text-xl font-semibold text-foreground">Batch document intake</h3>
            <p className="mt-3 text-muted-foreground leading-relaxed">
              Add PDFs and page images to a case together. Processing runs per document, so one file can be reviewed while others continue.
            </p>
          </div>
          
          <div className="group rounded-2xl border border-border bg-card p-7 transition-colors hover:bg-muted/40">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-purple-500/10 text-purple-400 ring-1 ring-purple-500/20 transition-transform group-hover:scale-110">
              <Zap size={28} />
            </div>
            <h3 className="mt-5 text-xl font-semibold text-foreground">OCR and extraction</h3>
            <p className="mt-3 text-muted-foreground leading-relaxed">
              Text recognition and assisted extraction organize names, dates, property details, and ownership-chain information for review.
            </p>
          </div>

          <div className="group rounded-2xl border border-border bg-card p-7 transition-colors hover:bg-muted/40">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20 transition-transform group-hover:scale-110">
              <ShieldCheck size={28} />
            </div>
            <h3 className="mt-5 text-xl font-semibold text-foreground">Human review</h3>
            <p className="mt-3 text-muted-foreground leading-relaxed">
              Reviewers can correct extracted fields and page text, inspect flagged items, and choose the text that goes into a report.
            </p>
          </div>

          <div className="group flex flex-col justify-center rounded-2xl border border-border bg-card p-7 transition-colors hover:bg-muted/40 md:col-span-2">
            <h3 className="text-xl font-semibold text-foreground">Keep findings tied to the source</h3>
            <p className="mt-3 text-muted-foreground leading-relaxed max-w-lg">
              Open a document&apos;s page text alongside its extracted fields, make corrections, and add selected excerpts to the report workspace.
            </p>
          </div>
        </div>
      </section>

      <Separator className="mx-auto max-w-7xl bg-border" />

      {/* Workflow Timeline */}
      <section id="workflow" className="relative mx-auto max-w-7xl px-6 py-24">
        {/* Subtle glow behind workflow */}
        <div className="absolute top-1/2 left-1/2 -z-10 h-[500px] w-[800px] -translate-x-1/2 -translate-y-1/2 opacity-10 blur-[100px] bg-emerald-500/30 rounded-full" />
        
        <div className="grid gap-16 lg:grid-cols-2 lg:items-center">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400">
              Operating Workflow
            </div>
            <h2 className="mt-6 text-4xl font-bold tracking-tight text-foreground md:text-5xl">From document intake to lawyer review.</h2>
            <p className="mt-6 text-lg text-muted-foreground leading-relaxed">
              EasyHuntV2 organizes the processing steps; a qualified reviewer checks the results and decides what belongs in the final report.
            </p>
            
            <div className="relative mt-12 flex flex-col before:absolute before:bottom-4 before:left-3.5 before:top-4 before:w-0.5 before:bg-border">
              {[
                { title: "Intake", detail: "Upload documents to a property case" },
                { title: "Processing", detail: "Enhance pages, recognize text, and extract fields" },
                { title: "Review", detail: "Check fields and source text; resolve flags" },
                { title: "Report", detail: "Select excerpts and prepare the report" },
              ].map(({ title, detail }, i) => (
                <div key={title} className="group relative flex gap-6 pb-10 last:pb-0">
                  <div className="relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 border-border bg-background text-xs font-semibold text-muted-foreground">
                    {i + 1}
                  </div>
                  <div className="-mt-1.5 transition-all group-hover:translate-x-1">
                    <h4 className="text-lg font-bold text-foreground">{title}</h4>
                    <p className="mt-1 text-sm text-muted-foreground">{detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="relative rounded-2xl border border-border bg-card p-6 shadow-lg md:p-8">
            <h3 className="mb-6 text-lg font-semibold text-foreground">What happens in a case</h3>
            <div className="space-y-5">
              {[
                { title: "Upload", detail: "Add the case documents together" },
                { title: "Process", detail: "Prepare page images and recognize document text" },
                { title: "Review", detail: "Verify extracted information and flagged items" },
                { title: "Report", detail: "Assemble approved, reviewer-selected excerpts" },
              ].map(({ title, detail }) => (
                <div key={title} className="flex items-start gap-3 rounded-xl border border-border bg-background p-4">
                  <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-emerald-500" />
                  <div>
                    <p className="text-sm font-semibold text-foreground">{title}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">{detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
