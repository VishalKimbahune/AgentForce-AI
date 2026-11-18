"use client";

import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { ThemeToggle } from "./theme-toggle";
import { User, LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth-context";

const pageTitles: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/employees": "AI employees",
  "/workflows": "Workflows",
  "/approvals": "Approval center",
  "/knowledge": "Knowledge base",
  "/analytics": "LLM analytics",
  "/settings": "Settings",
};

export function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const title = pageTitles[pathname] || "Dashboard";
  const { user, appUser, signOut } = useAuth();

  const handleAuthAction = async () => {
    if (user) {
      router.push("/settings");
    } else {
      router.push("/login");
    }
  };

  const userInitial = (appUser?.name || user?.email || "U").charAt(0).toUpperCase();

  return (
    <header className="h-14 border-b border-border bg-background px-6 flex items-center justify-between sticky top-0 z-10">
      <div>
        <h1 className="text-[18px] font-medium text-foreground tracking-tight">
          {title}
        </h1>
      </div>

      <div className="flex items-center gap-3">
        <ThemeToggle />
        {user ? (
          <div className="flex items-center gap-2">
            <button
              onClick={handleAuthAction}
              className="h-9 px-3 rounded-md border border-border flex items-center gap-2 text-[13px] text-muted-foreground hover:text-foreground hover:bg-muted transition-colors duration-theme"
              title={user.email || "User profile"}
            >
              <div className="w-5 h-5 rounded-full bg-muted flex items-center justify-center font-mono text-[11px] text-foreground font-medium">
                {userInitial}
              </div>
              <span className="max-w-[120px] truncate">{appUser?.name || user.email?.split("@")[0]}</span>
            </button>
            <button
              onClick={() => signOut()}
              aria-label="Sign out"
              className="h-9 w-9 rounded-md border border-border flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors duration-theme"
              title="Sign out"
            >
              <LogOut size={16} strokeWidth={1.5} />
            </button>
          </div>
        ) : (
          <Link
            href="/login"
            className="h-9 px-3 rounded-md border border-border flex items-center gap-2 text-[13px] text-foreground hover:bg-muted transition-colors duration-theme"
          >
            <User size={15} strokeWidth={1.5} />
            <span>Sign in</span>
          </Link>
        )}
      </div>
    </header>
  );
}
