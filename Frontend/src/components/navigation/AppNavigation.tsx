"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, Home, ListChecks, LogOut, ShieldCheck, UserRound } from "lucide-react";
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

// Shown only to an Admin: create lawyer accounts and assign cases.
const adminNavItem = { href: "/admin/users", label: "Admin", icon: ShieldCheck };

export function AppNavigation() {
  const pathname = usePathname();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const items = user?.role === "Admin" ? [...navItems, adminNavItem] : navItems;

  return (
    <header className="sticky top-0 z-50 border-b bg-background">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
        <Link href="/" className="font-heading text-xl font-medium tracking-tight">
          EasyHunt
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {items.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(`${item.href}/`));
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
            </>
          )}
        </div>
      </div>
    </header>
  );
}
