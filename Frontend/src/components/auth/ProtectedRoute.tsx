"use client";

import React, { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { Loader2, ShieldAlert } from "lucide-react";

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: string[];
}

export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, user, hasRole, accessDeniedModal } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading) {
      if (!isAuthenticated) {
        const returnTo = encodeURIComponent(pathname);
        router.replace(`/login?returnTo=${returnTo}`);
      } else if (allowedRoles && allowedRoles.length > 0 && !hasRole(allowedRoles)) {
        accessDeniedModal.trigger(
          `Your role (${user?.role}) does not have access to this screen (${pathname}).`
        );
      }
    }
  }, [isAuthenticated, isLoading, allowedRoles, hasRole, pathname, router, accessDeniedModal, user?.role]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <Loader2 size={32} className="animate-spin text-primary" />
          <p className="text-sm font-medium text-muted-foreground">Verifying security session…</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  if (allowedRoles && allowedRoles.length > 0 && !hasRole(allowedRoles)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6">
        <div className="w-full max-w-md text-center">
          <div className="mx-auto mb-4 flex size-14 items-center justify-center rounded-2xl bg-destructive/10 text-destructive">
            <ShieldAlert size={28} />
          </div>
          <h2 className="text-2xl font-bold tracking-tight">Access Restricted</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            You do not have permission to view this section. Role required:{" "}
            <span className="font-semibold text-foreground">{allowedRoles.join(", ")}</span> (Your role: {user?.role}).
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <button
              onClick={() => router.push("/dashboard")}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Return to Dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
