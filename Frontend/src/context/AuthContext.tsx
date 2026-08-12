"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { apiClient } from "@/services/api/client";

export type UserRole = "Vendor" | "Reviewer" | "Admin";

export interface User {
  id: string;
  email: string;
  role: UserRole;
  name?: string;
  organisation_name?: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<{ success: boolean; error?: string }>;
  signup: (data: { email: string; password: string; name?: string }) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  hasRole: (allowedRoles: string[]) => boolean;
  accessDeniedModal: {
    isOpen: boolean;
    message: string;
    close: () => void;
    trigger: (message?: string) => void;
  };
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const TOKEN_KEY = "propverify_token";
const USER_KEY = "propverify_user";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [accessDeniedState, setAccessDeniedState] = useState<{ isOpen: boolean; message: string }>({
    isOpen: false,
    message: "",
  });

  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Load session from localStorage on mount
    try {
      const storedToken = localStorage.getItem(TOKEN_KEY);
      const storedUserRaw = localStorage.getItem(USER_KEY);
      const storedRole = localStorage.getItem("propverify_role");

      if (storedToken) {
        setToken(storedToken);
        if (storedUserRaw) {
          setUser(JSON.parse(storedUserRaw));
        } else if (storedRole) {
          setUser({
            id: localStorage.getItem("propverify_user_id") || "1",
            email: "user@propverify.ai",
            role: (storedRole as UserRole) || "Vendor",
          });
        }
      }
    } catch (err) {
      console.error("Failed to restore auth session:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Listen for custom 401 and 403 events from API client interceptors
  useEffect(() => {
    function handleUnauthorized() {
      setToken(null);
      setUser(null);
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      localStorage.removeItem("propverify_role");
      localStorage.removeItem("propverify_user_id");

      const returnTo = encodeURIComponent(window.location.pathname + window.location.search);
      router.push(`/login?returnTo=${returnTo}`);
    }

    function handleForbidden(e: Event) {
      const customEvent = e as CustomEvent<{ message?: string }>;
      setAccessDeniedState({
        isOpen: true,
        message: customEvent.detail?.message || "You do not have permission to access this resource or perform this action.",
      });
    }

    window.addEventListener("auth:unauthorized", handleUnauthorized);
    window.addEventListener("auth:forbidden", handleForbidden);

    return () => {
      window.removeEventListener("auth:unauthorized", handleUnauthorized);
      window.removeEventListener("auth:forbidden", handleForbidden);
    };
  }, [router]);

  async function login(email: string, password: string) {
    const result = await apiClient.auth.login(email, password);
    if (result.success && result.token && result.user) {
      const formattedUser: User = {
        id: result.user.id,
        email: result.user.email,
        role: (result.user.role as UserRole) || "Vendor",
        name: result.user.email.split("@")[0],
      };

      setToken(result.token);
      setUser(formattedUser);

      localStorage.setItem(TOKEN_KEY, result.token);
      localStorage.setItem(USER_KEY, JSON.stringify(formattedUser));
      localStorage.setItem("propverify_role", formattedUser.role);
      localStorage.setItem("propverify_user_id", formattedUser.id);
      return { success: true };
    }
    return { success: false, error: result.error || "Login failed" };
  }

  async function signup(data: { email: string; password: string; name?: string }) {
    const result = await apiClient.auth.signup(data);
    if (result.success) {
      if (result.user && result.token) {
        const formattedUser: User = {
          id: result.user.id,
          email: result.user.email,
          role: "Vendor",
          name: data.name || result.user.name || result.user.email.split("@")[0],
        };
        setToken(result.token);
        setUser(formattedUser);
        localStorage.setItem(TOKEN_KEY, result.token);
        localStorage.setItem(USER_KEY, JSON.stringify(formattedUser));
        localStorage.setItem("propverify_role", formattedUser.role);
        localStorage.setItem("propverify_user_id", formattedUser.id);
      }
      return { success: true };
    }
    return { success: false, error: result.error || "Signup failed" };
  }

  async function logout() {
    try {
      await apiClient.auth.logout();
    } catch {
      // Proceed even if server logout endpoint fails
    }
    setToken(null);
    setUser(null);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem("propverify_role");
    localStorage.removeItem("propverify_user_id");
    router.push("/");
  }

  function hasRole(allowedRoles: string[]): boolean {
    if (!user) return false;
    const currentRoleLower = user.role.toLowerCase();
    return allowedRoles.some((r) => r.toLowerCase() === currentRoleLower);
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        isLoading,
        login,
        signup,
        logout,
        hasRole,
        accessDeniedModal: {
          isOpen: accessDeniedState.isOpen,
          message: accessDeniedState.message,
          close: () => setAccessDeniedState((prev) => ({ ...prev, isOpen: false })),
          trigger: (message?: string) =>
            setAccessDeniedState({
              isOpen: true,
              message: message || "You do not have permission to perform this action.",
            }),
        },
      }}
    >
      {children}
      {/* Global Access Denied (403) Modal */}
      {accessDeniedState.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-200">
          <div className="w-full max-w-md rounded-xl border border-destructive/30 bg-background p-6 shadow-2xl">
            <div className="flex items-center gap-3 text-destructive">
              <span className="flex size-10 items-center justify-center rounded-lg bg-destructive/10">
                <svg className="size-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </span>
              <div>
                <h3 className="text-lg font-bold">Access Denied (403)</h3>
                <p className="text-xs text-muted-foreground">Insufficient Permission</p>
              </div>
            </div>
            <p className="mt-4 text-sm text-foreground/90">
              {accessDeniedState.message}
            </p>
            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setAccessDeniedState((prev) => ({ ...prev, isOpen: false }))}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
              >
                Acknowledge
              </button>
            </div>
          </div>
        </div>
      )}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

export function useHasRole(allowedRoles: string[]): boolean {
  const { hasRole } = useAuth();
  return hasRole(allowedRoles);
}
