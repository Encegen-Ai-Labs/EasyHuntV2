"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, FileCheck2, Home, ListChecks, UploadCloud, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Home", icon: Home },
  { href: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { href: "/cases", label: "Cases", icon: ListChecks },
  { href: "/cases/upload", label: "Upload", icon: UploadCloud },
  { href: "/cases/PV-2408/status", label: "Status", icon: FileCheck2 },
  { href: "/cases/PV-2408/review", label: "Review", icon: FileCheck2 },
  { href: "/cases/PV-2408/report", label: "Report", icon: FileCheck2 },
];

export function AppNavigation() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <FileCheck2 size={18} />
          </span>
          <div>
            <div className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
              PropVerify AI
            </div>
            <div className="text-sm font-semibold leading-none">Risk Intelligence</div>
          </div>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                  isActive
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )}
              >
                <Icon size={13} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" className="hidden md:inline-flex" render={<Link href="/login" />}>
            Login
          </Button>
          <Button size="sm" render={<Link href="/signup" />}>
            <UserRound data-icon="inline-start" />
            Workspace
          </Button>
        </div>
      </div>
    </header>
  );
}
