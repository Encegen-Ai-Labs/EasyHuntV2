"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <Button variant="outline" size="sm" className="h-9 px-3 opacity-50" aria-label="Toggle theme">
        <Sun size={14} />
      </Button>
    );
  }

  const isDark = (resolvedTheme || theme) === "dark";

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className="flex items-center gap-1.5 transition-all duration-200"
      title={`Switch to ${isDark ? "Light" : "Dark"} theme`}
      aria-label="Toggle theme"
    >
      {isDark ? (
        <>
          <Sun size={14} className="text-amber-400 transition-transform duration-300 hover:rotate-45" />
          <span className="text-xs font-semibold">Light</span>
        </>
      ) : (
        <>
          <Moon size={14} className="text-slate-800 dark:text-slate-200 transition-transform duration-300" />
          <span className="text-xs font-semibold">Dark</span>
        </>
      )}
    </Button>
  );
}
