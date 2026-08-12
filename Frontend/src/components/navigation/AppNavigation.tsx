"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  FileCheck2,
  Home,
  ListChecks,
  LogOut,
  UploadCloud,
  UserRound,
  FileSearch,
  Shield,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useAuth } from "@/context/AuthContext";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function AppNavigation() {
  const pathname = usePathname();
  const { isAuthenticated, user, logout, isLoading } = useAuth();

  const allNavItems = [
    { href: "/", label: "Home", icon: Home, roles: ["public", "vendor", "reviewer", "admin"] },
    { href: "/dashboard", label: "Dashboard", icon: BarChart3, roles: ["vendor", "reviewer", "admin"] },
    { href: "/cases", label: "Cases", icon: ListChecks, roles: ["vendor", "reviewer", "admin"] },
    { href: "/cases/upload", label: "Upload Document", icon: UploadCloud, roles: ["vendor", "admin"] },
    { href: "/review", label: "Review Queue", icon: FileCheck2, roles: ["reviewer", "admin"] },
    { href: "/admin/users", label: "User Directory", icon: UserRound, roles: ["admin"] },
    { href: "/reports", label: "Reports", icon: FileSearch, roles: ["admin"] },
  ];

  const visibleNavItems = isAuthenticated
    ? allNavItems.filter((item) => item.roles.includes(user?.role?.toLowerCase() || ""))
    : [];

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

        {/* Center Nav Links */}
        <nav className="hidden items-center gap-1 md:flex">
          {isAuthenticated ? (
            visibleNavItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                    isActive
                      ? "bg-accent text-accent-foreground font-semibold"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  )}
                >
                  <Icon size={14} />
                  {item.label}
                </Link>
              );
            })
          ) : (
            <Link
              href="/"
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                pathname === "/"
                  ? "bg-accent text-accent-foreground font-semibold"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <Home size={14} />
              Home
            </Link>
          )}
        </nav>

        {/* Header Right Actions */}
        <div className="flex items-center gap-3">
          <ThemeToggle />

          {isLoading ? (
            <Loader2 size={16} className="animate-spin text-muted-foreground" />
          ) : isAuthenticated && user ? (
            <div className="flex items-center gap-3">
              <div className="hidden sm:flex items-center gap-2 rounded-lg border border-border bg-card px-2.5 py-1">
                <Shield size={13} className="text-primary" />
                <span className="text-xs font-medium text-foreground max-w-[120px] truncate">
                  {user.email}
                </span>
                <Badge
                  variant={
                    user.role === "Admin"
                      ? "destructive"
                      : user.role === "Reviewer"
                      ? "default"
                      : "secondary"
                  }
                  className="text-[10px] uppercase font-bold"
                >
                  {user.role}
                </Badge>
              </div>

              <Button
                variant="ghost"
                size="sm"
                onClick={() => logout()}
                className="text-muted-foreground hover:text-destructive"
              >
                <LogOut size={14} data-icon="inline-start" />
                <span className="hidden sm:inline">Logout</span>
              </Button>
            </div>
          ) : (
            /* Unauthenticated: Home, Login, Signup buttons ONLY */
            <div className="flex items-center gap-2">
              <Link
                href="/login"
                className="inline-flex h-8 items-center justify-center rounded-lg px-3 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
              >
                Login
              </Link>
              <Link
                href="/signup"
                className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg bg-primary px-3 text-xs font-medium text-primary-foreground shadow-xs transition-colors hover:bg-primary/90"
              >
                <UserRound size={14} />
                Signup
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
