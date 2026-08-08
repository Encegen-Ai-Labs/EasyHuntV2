import Link from "next/link";
import Image from "next/image";
import { ArrowRight, BarChart3, CheckCircle2, ClipboardCheck, FileSearch, FolderOpen, ShieldCheck, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
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
      <section className="relative px-6 pt-32 pb-24 lg:pt-40 lg:pb-32">
        <div className="mx-auto max-w-7xl grid grid-cols-1 gap-16 lg:grid-cols-2 lg:items-center">
          
          {/* Copy Content */}
          <div className="flex flex-col z-10 relative">
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-xs font-medium text-indigo-300 w-fit backdrop-blur-sm shadow-[0_0_15px_-3px_rgba(99,102,241,0.2)]">
              <span className="flex h-2 w-2 rounded-full bg-indigo-500 animate-ping absolute"></span>
              <span className="flex h-2 w-2 rounded-full bg-indigo-500 relative"></span>
              PropVerify Intelligence v2.0
            </div>
            
            <h1 className="mt-8 text-5xl font-extrabold tracking-tight leading-[1.1] lg:text-6xl xl:text-7xl text-transparent bg-clip-text bg-gradient-to-br from-white via-white to-slate-500">
              Turn quiet records into clear risk.
            </h1>
            
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground">
              PropVerify reads the property file before the review team does. Entity matching, lien exposure, and ownership extraction that turns a file from reactive to ready.
            </p>
            
            <div className="mt-10 flex flex-wrap items-center gap-4">
              <Button size="lg" className="h-12 px-8 rounded-full bg-white text-black hover:bg-slate-200 transition-all hover:scale-105 hover:shadow-[0_0_20px_-5px_rgba(255,255,255,0.4)]" render={<Link href="/cases/new" />}>
                Open a case
                <ArrowRight className="ml-2 size-4" />
              </Button>
              <Button variant="outline" size="lg" className="h-12 px-8 rounded-full border-white/20 bg-white/5 backdrop-blur-md hover:bg-white/10 transition-all" render={<Link href="/dashboard" />}>
                Review desk
              </Button>
            </div>
            
            {/* Quick Metrics */}
            <div className="mt-16 flex gap-10 border-t border-border pt-8">
              <div className="flex flex-col">
                <span className="text-3xl font-bold text-white tracking-tight">226</span>
                <span className="mt-1 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Cases Checked</span>
              </div>
              <div className="flex flex-col">
                <span className="text-3xl font-bold text-white tracking-tight">2.3k</span>
                <span className="mt-1 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Docs Indexed</span>
              </div>
              <div className="flex flex-col hidden sm:flex">
                <span className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-emerald-600 tracking-tight">100%</span>
                <span className="mt-1 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Confidence</span>
              </div>
            </div>
          </div>

          {/* 3D Glassmorphism Image / Dashboard Preview */}
          <div className="relative z-10 lg:ml-auto perspective-[1000px]">
            <div className="absolute -inset-1 bg-gradient-to-r from-indigo-500 to-purple-600 rounded-[2rem] blur opacity-30 animate-pulse"></div>
            <div className="relative transform-gpu transition-all duration-700 hover:rotate-y-0 hover:rotate-x-0 rotate-y-[-10deg] rotate-x-[5deg] rounded-[2rem] border border-white/10 bg-black/40 p-2 shadow-2xl backdrop-blur-2xl">
              <div className="absolute top-4 left-4 flex gap-1.5">
                <div className="h-3 w-3 rounded-full bg-rose-500/80"></div>
                <div className="h-3 w-3 rounded-full bg-amber-500/80"></div>
                <div className="h-3 w-3 rounded-full bg-emerald-500/80"></div>
              </div>
              <div className="overflow-hidden rounded-2xl border border-white/5 mt-6 relative">
                <Image 
                  src="/images/hero_abstract.png" 
                  alt="PropVerify AI Data Visualization" 
                  width={600} 
                  height={500}
                  className="object-cover opacity-90 transition-transform duration-1000 hover:scale-105"
                  priority
                />
                {/* Floating Glass Badges */}
                <div className="absolute bottom-6 left-6 rounded-xl border border-white/10 bg-black/60 p-4 backdrop-blur-md shadow-2xl">
                   <div className="flex items-center gap-3">
                     <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/20 text-emerald-400">
                       <CheckCircle2 size={20} />
                     </div>
                     <div>
                       <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Risk Status</p>
                       <p className="text-lg font-bold text-white">Clear & Ready</p>
                     </div>
                   </div>
                </div>
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* Features Bento Grid */}
      <section id="platform" className="relative mx-auto max-w-7xl px-6 py-24">
        <div className="mb-16 max-w-2xl">
          <h2 className="text-3xl font-bold tracking-tight md:text-5xl text-white">The file desk, connected</h2>
          <p className="mt-4 text-lg text-muted-foreground leading-relaxed">
            A unified operating system for property diligence. Intake documents, run OCR, extract fields with LLMs, and audit risk in one cohesive workflow.
          </p>
        </div>
        
        <div className="grid gap-6 md:grid-cols-3">
          <div className="group rounded-[2rem] border border-white/5 bg-white/[0.02] p-8 transition-all hover:bg-white/[0.04] hover:shadow-[0_0_40px_-15px_rgba(255,255,255,0.1)] md:col-span-2">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-400 ring-1 ring-indigo-500/20 transition-transform group-hover:scale-110">
              <FileSearch size={28} />
            </div>
            <h3 className="mt-6 text-2xl font-bold text-white">Intelligent Document Intake</h3>
            <p className="mt-3 text-muted-foreground leading-relaxed">
              Drop deeds, surveys, valuation reports, and tax receipts into a single surface. We automatically classify the document type and prepare it for deep extraction.
            </p>
          </div>
          
          <div className="group rounded-[2rem] border border-white/5 bg-white/[0.02] p-8 transition-all hover:bg-white/[0.04] hover:shadow-[0_0_40px_-15px_rgba(255,255,255,0.1)]">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-purple-500/10 text-purple-400 ring-1 ring-purple-500/20 transition-transform group-hover:scale-110">
              <Zap size={28} />
            </div>
            <h3 className="mt-6 text-2xl font-bold text-white">AI Extraction</h3>
            <p className="mt-3 text-muted-foreground leading-relaxed">
              Proprietary vision models read unstructured text to extract ownership history, property boundaries, and lien data instantly.
            </p>
          </div>

          <div className="group rounded-[2rem] border border-white/5 bg-white/[0.02] p-8 transition-all hover:bg-white/[0.04] hover:shadow-[0_0_40px_-15px_rgba(255,255,255,0.1)]">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20 transition-transform group-hover:scale-110">
              <ShieldCheck size={28} />
            </div>
            <h3 className="mt-6 text-2xl font-bold text-white">Risk Audit</h3>
            <p className="mt-3 text-muted-foreground leading-relaxed">
              Analysts get a prioritized list of what needs clearance, flagging discrepancies before manual review.
            </p>
          </div>

          <div className="group flex flex-col justify-center rounded-[2rem] border border-white/5 bg-gradient-to-br from-indigo-500/5 to-purple-500/5 p-8 transition-all hover:bg-white/[0.04] md:col-span-2">
            <h3 className="text-2xl font-bold text-white">End-to-End Deal Security</h3>
            <p className="mt-3 text-muted-foreground leading-relaxed max-w-lg">
              Every field extracted is linked to its source document with high-confidence bounding boxes, ensuring full traceability.
            </p>
            <div className="mt-6">
              <Button variant="secondary" className="rounded-full bg-white/10 hover:bg-white/20" render={<Link href="/cases/new" />}>
                Start a free analysis
              </Button>
            </div>
          </div>
        </div>
      </section>

      <Separator className="bg-white/5 max-w-7xl mx-auto" />

      {/* Workflow Timeline */}
      <section id="workflow" className="relative mx-auto max-w-7xl px-6 py-24">
        {/* Subtle glow behind workflow */}
        <div className="absolute top-1/2 left-1/2 -z-10 h-[500px] w-[800px] -translate-x-1/2 -translate-y-1/2 opacity-20 blur-[100px] bg-emerald-500/30 rounded-full" />
        
        <div className="grid gap-16 lg:grid-cols-2 lg:items-center">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400">
              Operating Workflow
            </div>
            <h2 className="mt-6 text-4xl font-bold tracking-tight md:text-5xl text-white">From intake packet <br/>to recommendation.</h2>
            <p className="mt-6 text-lg text-muted-foreground leading-relaxed">
              The PropVerify desk builds a complete review trail. Facts arrive, fields are checked, exposure is interpreted, and a report is prepared automatically.
            </p>
            
            <div className="mt-12 flex flex-col relative before:absolute before:left-3.5 before:top-4 before:bottom-4 before:w-0.5 before:bg-white/10">
              {[
                { title: "Intake", detail: "Document collection & source validation", active: true },
                { title: "Extraction", detail: "Entity, title, value, & lien mapping", active: true },
                { title: "Audit", detail: "Confidence calibration & flag review", active: false },
                { title: "Report", detail: "Executive summary export", active: false },
              ].map(({ title, detail, active }, i) => (
                <div key={title} className="group relative flex gap-6 pb-10 last:pb-0">
                  <div className={`relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 ${active ? 'border-emerald-500 bg-black' : 'border-white/20 bg-black'}`}>
                    {active ? <div className="h-2 w-2 rounded-full bg-emerald-500" /> : null}
                  </div>
                  <div className="-mt-1.5 transition-all group-hover:translate-x-1">
                    <h4 className={`text-lg font-bold ${active ? 'text-white' : 'text-muted-foreground'}`}>{title}</h4>
                    <p className="mt-1 text-sm text-muted-foreground">{detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="relative rounded-[2rem] border border-white/10 bg-black/40 p-8 shadow-2xl backdrop-blur-xl">
            <h3 className="text-xl font-bold text-white mb-6">Review Pipeline</h3>
            <div className="space-y-6">
              
              <div>
                <div className="flex justify-between text-sm font-medium text-white mb-3">
                  <span>OCR Processing</span>
                  <span className="text-emerald-400">100%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-white/10">
                  <div className="h-full w-full rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.8)]" />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-sm font-medium text-white mb-3">
                  <span>Entity Extraction</span>
                  <span className="text-indigo-400">82%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-white/10">
                  <div className="h-full w-[82%] rounded-full bg-indigo-500 shadow-[0_0_10px_rgba(99,102,241,0.8)]" />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-sm font-medium text-white mb-3">
                  <span>Risk Calibration</span>
                  <span className="text-muted-foreground">Pending</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-white/10">
                  <div className="h-full w-[10%] rounded-full bg-white/20" />
                </div>
              </div>

            </div>

            <div className="mt-10 rounded-xl border border-white/5 bg-white/5 p-4 flex justify-between items-center">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">System Health</p>
                <p className="text-lg font-bold text-white">All systems operational</p>
              </div>
              <div className="h-3 w-3 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.8)] animate-pulse" />
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
