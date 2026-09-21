"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, FileCheck2, Home, ListChecks, LogOut, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ThemeToggle";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";

// Upload/Status/Review/Report were removed from here (2026-08-21, user's
// explicit request) — each pointed at a hardcoded demo case id
// ("/cases/PV-2408/...") regardless of which case was actually open, and
// each screen is reachable through the real per-case flow instead: Upload
// via a case's workspace (CaseWorkspacePage.tsx), Review via "Open Review
// Workspace" there, Report via the Report Builder link on the review page
// (ReviewPage.tsx, see item 9).
const navItems = [
  { href: "/", label: "Home", icon: Home },
  { href: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { href: "/cases", label: "Cases", icon: ListChecks },
];

export function AppNavigation() {
  const pathname = usePathname();
  const { user, isAuthenticated, isLoading, logout } = useAuth();

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
          <ThemeToggle />
          {!isLoading && isAuthenticated ? (
            <>
              <span className="hidden items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-muted-foreground md:inline-flex">
                <UserRound size={13} />
                {user?.email}
              </span>
              <Button size="sm" nativeButton={false} render={<Link href="/dashboard" />}>
                <BarChart3 data-icon="inline-start" />
                Workspace
              </Button>
              <Button variant="ghost" size="sm" onClick={() => logout()}>
                <LogOut data-icon="inline-start" />
                Logout
              </Button>
            </>
          ) : (
            <>
              <Button variant="ghost" size="sm" className="hidden md:inline-flex" nativeButton={false} render={<Link href="/login" />}>
                Login
              </Button>
              <Button size="sm" nativeButton={false} render={<Link href="/login" />}>
                <UserRound data-icon="inline-start" />
                Workspace
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
