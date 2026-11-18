"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { ThemeToggle } from "@/components/theme-toggle";
import { ArrowRight, Loader2 } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { signIn, demoSignIn, signUp, user } = useAuth();

  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);

  // If already authenticated, redirect to dashboard
  if (user) {
    router.push("/dashboard");
  }

  const handleDemoLogin = async (demoEmail: string) => {
    setErrorMsg(null);
    setDemoLoading(true);
    try {
      const { error } = await demoSignIn(demoEmail);
      if (error) {
        setErrorMsg(error.message);
      } else {
        router.push("/dashboard");
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Demo login failed");
    } finally {
      setDemoLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setLoading(true);

    try {
      if (isSignUp) {
        const { error } = await signUp(email, password, fullName, orgName);
        if (error) {
          setErrorMsg(error.message);
        } else {
          router.push("/dashboard");
        }
      } else {
        const { error } = await signIn(email, password);
        if (error) {
          setErrorMsg(error.message);
        } else {
          router.push("/dashboard");
        }
      }
    } catch (err: any) {
      setErrorMsg(err.message || "An unexpected error occurred");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col justify-between">
      {/* Top navigation */}
      <header className="h-14 px-6 border-b border-border flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-medium text-foreground">
          <div className="w-4 h-4 bg-foreground rounded-[2px]" />
          <span className="text-[15px] font-medium tracking-tight">AgentForce AI</span>
        </Link>
        <ThemeToggle />
      </header>

      {/* Main card */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-[400px] border border-border rounded-lg bg-card p-8 space-y-6">
          <div className="space-y-1.5">
            <h1 className="text-[20px] font-medium text-foreground tracking-tight">
              {isSignUp ? "Create organization account" : "Sign in to workspace"}
            </h1>
            <p className="text-[13px] text-muted-foreground">
              {isSignUp
                ? "Deploy and manage your autonomous workforce."
                : "Enter your credentials to access your AI employees."}
            </p>
          </div>

          {errorMsg && (
            <div className="p-3 rounded-md border border-danger/40 bg-muted/40 text-[13px] text-danger flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-danger mt-1.5 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {isSignUp && (
              <>
                <div className="space-y-1">
                  <label className="text-[12px] text-muted-foreground block">Full name</label>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Priya Sharma"
                    className="w-full h-9 px-3 rounded-md border border-border bg-background text-[14px] text-foreground focus:outline-none focus:ring-2 focus:ring-ring placeholder:text-muted-foreground"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[12px] text-muted-foreground block">Workspace / organization</label>
                  <input
                    type="text"
                    required
                    value={orgName}
                    onChange={(e) => setOrgName(e.target.value)}
                    placeholder="Acme Technologies"
                    className="w-full h-9 px-3 rounded-md border border-border bg-background text-[14px] text-foreground focus:outline-none focus:ring-2 focus:ring-ring placeholder:text-muted-foreground"
                  />
                </div>
              </>
            )}

            <div className="space-y-1">
              <label className="text-[12px] text-muted-foreground block">Work email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="priya@acme.com"
                className="w-full h-9 px-3 rounded-md border border-border bg-background text-[14px] text-foreground focus:outline-none focus:ring-2 focus:ring-ring placeholder:text-muted-foreground"
              />
            </div>

            <div className="space-y-1">
              <label className="text-[12px] text-muted-foreground block">Password</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full h-9 px-3 rounded-md border border-border bg-background text-[14px] text-foreground focus:outline-none focus:ring-2 focus:ring-ring placeholder:text-muted-foreground"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full h-9 mt-2 rounded-md bg-primary text-primary-foreground text-[14px] font-medium flex items-center justify-center gap-2 hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {loading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <>
                  <span>{isSignUp ? "Create account" : "Sign in"}</span>
                  <ArrowRight size={14} />
                </>
              )}
            </button>
          </form>

          <div className="pt-2 border-t border-border text-center">
            <button
              type="button"
              onClick={() => {
                setIsSignUp(!isSignUp);
                setErrorMsg(null);
              }}
              className="text-[13px] text-muted-foreground hover:text-foreground transition-colors"
            >
              {isSignUp
                ? "Already have an account? Sign in"
                : "Don't have an organization workspace? Sign up"}
            </button>
          </div>

          {/* 1-Click Demo Personas (No Supabase Cloud Required) */}
          <div className="pt-4 border-t border-border space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                Instant 1-Click Demo Login
              </span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                No Cloud Setup
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => handleDemoLogin("vikram@acme.corp")}
                disabled={demoLoading || loading}
                className="p-2.5 border border-border rounded-md text-left hover:bg-muted transition-colors text-[12px] group"
              >
                <div className="font-medium text-foreground group-hover:text-primary transition-colors">
                  Vikram Patel
                </div>
                <div className="text-[10px] text-muted-foreground">Owner (Full Admin)</div>
              </button>
              <button
                type="button"
                onClick={() => handleDemoLogin("priya@acme.corp")}
                disabled={demoLoading || loading}
                className="p-2.5 border border-border rounded-md text-left hover:bg-muted transition-colors text-[12px] group"
              >
                <div className="font-medium text-foreground group-hover:text-primary transition-colors">
                  Priya Sharma
                </div>
                <div className="text-[10px] text-muted-foreground">HR Manager</div>
              </button>
              <button
                type="button"
                onClick={() => handleDemoLogin("rahul@acme.corp")}
                disabled={demoLoading || loading}
                className="p-2.5 border border-border rounded-md text-left hover:bg-muted transition-colors text-[12px] group"
              >
                <div className="font-medium text-foreground group-hover:text-primary transition-colors">
                  Rahul Verma
                </div>
                <div className="text-[10px] text-muted-foreground">Finance Manager</div>
              </button>
              <button
                type="button"
                onClick={() => handleDemoLogin("amit@acme.corp")}
                disabled={demoLoading || loading}
                className="p-2.5 border border-border rounded-md text-left hover:bg-muted transition-colors text-[12px] group"
              >
                <div className="font-medium text-foreground group-hover:text-primary transition-colors">
                  Amit Deshmukh
                </div>
                <div className="text-[10px] text-muted-foreground">Compliance Auditor</div>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="p-6 text-center text-[12px] text-muted-foreground border-t border-border">
        AgentForce AI • Multi-tenant Enterprise SaaS
      </footer>
    </div>
  );
}

