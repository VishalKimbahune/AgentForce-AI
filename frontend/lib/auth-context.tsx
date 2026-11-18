"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

export interface Organization {
  id: string;
  name: string;
  plan: string;
  daily_token_budget: number;
  created_at?: string;
}

export interface Membership {
  id: string;
  tenant_id: string;
  user_id: string;
  role: string;
  organization?: Organization | null;
}

export interface AppUser {
  id: string;
  email: string;
  name?: string | null;
  mfa_enabled?: boolean;
  created_at?: string;
}

export interface AuthSession {
  access_token: string;
  token_type?: string;
  user?: {
    id: string;
    email?: string;
  };
}

export interface AuthUser {
  id: string;
  email?: string;
}

interface AuthResult {
  error: { message: string } | null;
}

interface AuthContextType {
  user: AuthUser | null;
  appUser: AppUser | null;
  session: AuthSession | null;
  memberships: Membership[];
  activeTenantId: string | null;
  loading: boolean;
  setActiveTenantId: (tenantId: string | null) => void;
  signIn: (email: string, password: string) => Promise<AuthResult>;
  signUp: (email: string, password: string, fullName: string, orgName: string) => Promise<AuthResult>;
  demoSignIn: (email: string) => Promise<AuthResult>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const DEMO_TOKEN_KEY = "agentforce_demo_token";
const ACTIVE_TENANT_KEY = "agentforce_active_tenant_id";

function getSupabaseClient(): SupabaseClient | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key || url.includes("your-project-ref") || key.includes("your-supabase")) {
    return null;
  }
  return createClient(url, key);
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [appUser, setAppUser] = useState<AppUser | null>(null);
  const [session, setSession] = useState<AuthSession | null>(null);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [activeTenantId, setActiveTenantIdState] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const setActiveTenantId = useCallback((tenantId: string | null) => {
    setActiveTenantIdState(tenantId);
    if (typeof window !== "undefined") {
      if (tenantId) {
        localStorage.setItem(ACTIVE_TENANT_KEY, tenantId);
      } else {
        localStorage.removeItem(ACTIVE_TENANT_KEY);
      }
    }
  }, []);

  const hydrateFromToken = useCallback(async (token: string): Promise<boolean> => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) {
        return false;
      }
      const data = await res.json();
      const fetchedUser: AppUser = data.user;
      const fetchedMemberships: Membership[] = data.memberships || [];
      const savedTenant =
        typeof window !== "undefined" ? localStorage.getItem(ACTIVE_TENANT_KEY) : null;
      const validSavedTenant = fetchedMemberships.some((m) => m.tenant_id === savedTenant)
        ? savedTenant
        : null;
      const resolvedTenantId =
        validSavedTenant || data.active_tenant_id || fetchedMemberships[0]?.tenant_id || null;

      setUser({ id: fetchedUser.id, email: fetchedUser.email });
      setAppUser(fetchedUser);
      setSession({
        access_token: token,
        token_type: "bearer",
        user: { id: fetchedUser.id, email: fetchedUser.email },
      });
      setMemberships(fetchedMemberships);
      setActiveTenantId(resolvedTenantId);
      return true;
    } catch {
      return false;
    }
  }, [setActiveTenantId]);

  const refreshProfile = useCallback(async () => {
    if (session?.access_token) {
      await hydrateFromToken(session.access_token);
    }
  }, [session?.access_token, hydrateFromToken]);

  useEffect(() => {
    let mounted = true;
    const initAuth = async () => {
      try {
        if (typeof window !== "undefined") {
          const demoToken = localStorage.getItem(DEMO_TOKEN_KEY);
          if (demoToken) {
            const ok = await hydrateFromToken(demoToken);
            if (ok) {
              if (mounted) setLoading(false);
              return;
            }
            localStorage.removeItem(DEMO_TOKEN_KEY);
          }
        }

        const supabase = getSupabaseClient();
        if (supabase) {
          const { data } = await supabase.auth.getSession();
          if (data.session?.access_token) {
            await hydrateFromToken(data.session.access_token);
          }
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };
    initAuth();
    return () => {
      mounted = false;
    };
  }, [hydrateFromToken]);

  const demoSignIn = useCallback(
    async (email: string): Promise<AuthResult> => {
      try {
        const res = await fetch(`${API_BASE}/api/v1/auth/demo-login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email }),
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          return {
            error: {
              message: errData.error?.message || errData.detail || "Demo login failed",
            },
          };
        }
        const data = await res.json();
        const token: string = data.access_token;
        if (typeof window !== "undefined") {
          localStorage.setItem(DEMO_TOKEN_KEY, token);
        }
        const ok = await hydrateFromToken(token);
        if (!ok) {
          setUser({ id: data.user.id, email: data.user.email });
          setAppUser(data.user);
          setSession({
            access_token: token,
            token_type: data.token_type || "bearer",
            user: { id: data.user.id, email: data.user.email },
          });
          setActiveTenantId(data.active_tenant_id || null);
        }
        return { error: null };
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Network error during demo login";
        return { error: { message } };
      }
    },
    [hydrateFromToken, setActiveTenantId]
  );

  const signIn = useCallback(
    async (email: string, password: string): Promise<AuthResult> => {
      const supabase = getSupabaseClient();
      if (!supabase) {
        // Fallback to local demo login when Supabase cloud credentials are not configured
        return demoSignIn(email);
      }
      const { data, error } = await supabase.auth.signInWithPassword({ email, password });
      if (error || !data.session?.access_token) {
        return { error: { message: error?.message || "Invalid credentials" } };
      }
      await hydrateFromToken(data.session.access_token);
      return { error: null };
    },
    [demoSignIn, hydrateFromToken]
  );

  const signUp = useCallback(
    async (
      email: string,
      password: string,
      fullName: string,
      orgName: string
    ): Promise<AuthResult> => {
      const supabase = getSupabaseClient();
      if (supabase) {
        const { data, error } = await supabase.auth.signUp({ email, password });
        if (error) {
          return { error: { message: error.message } };
        }
        const token = data.session?.access_token;
        if (token) {
          await fetch(`${API_BASE}/api/v1/auth/complete-profile`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ name: fullName, organization_name: orgName }),
          });
          await hydrateFromToken(token);
        }
        return { error: null };
      }

      // Local database registration when Supabase cloud is not configured
      try {
        const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email,
            password,
            name: fullName,
            organization_name: orgName,
          }),
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          return {
            error: {
              message: errData.error?.message || errData.detail || "Registration failed",
            },
          };
        }
        const data = await res.json();
        const token: string = data.access_token;
        if (typeof window !== "undefined") {
          localStorage.setItem(DEMO_TOKEN_KEY, token);
        }
        const ok = await hydrateFromToken(token);
        if (!ok) {
          setUser({ id: data.user.id, email: data.user.email });
          setAppUser(data.user);
          setSession({
            access_token: token,
            token_type: data.token_type || "bearer",
            user: { id: data.user.id, email: data.user.email },
          });
          setActiveTenantId(data.active_tenant_id || null);
        }
        return { error: null };
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Network error during registration";
        return { error: { message } };
      }
    },
    [hydrateFromToken, setActiveTenantId]
  );

  const signOut = useCallback(async () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(DEMO_TOKEN_KEY);
      localStorage.removeItem(ACTIVE_TENANT_KEY);
    }
    const supabase = getSupabaseClient();
    if (supabase) {
      await supabase.auth.signOut().catch(() => {});
    }
    setUser(null);
    setAppUser(null);
    setSession(null);
    setMemberships([]);
    setActiveTenantIdState(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        appUser,
        session,
        memberships,
        activeTenantId,
        loading,
        setActiveTenantId,
        signIn,
        signUp,
        demoSignIn,
        signOut,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
