"use client";

import { useEffect, useState, useRef } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  Upload,
  FileText,
  Search,
  CheckCircle2,
  AlertCircle,
  Trash2,
  RefreshCw,
  Sparkles,
  BookOpen,
  Shield,
  Layers,
  ArrowRight,
} from "lucide-react";

interface DocumentItem {
  id: string;
  name: string;
  mime_type: string;
  status: "processing" | "ready" | "failed";
  version: number;
  allowed_roles: string[];
  tags: string[];
  uploaded_by?: string;
  created_at: string;
  chunk_count: number;
}

interface SourceSnippet {
  source_name: string;
  page: number;
  chunk_index: number;
  score: number;
  citation: string;
  text_snippet: string;
}

interface AskResult {
  query: string;
  answer: string;
  citations: string[];
  chunks_used: number;
  sources: SourceSnippet[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const QUICK_QUESTIONS = [
  "What are the rules for interview scheduling?",
  "What is our policy on remote work eligibility?",
  "When are annual bonuses and compensation disbursed?",
];

export default function KnowledgePage() {
  const { session, activeTenantId, memberships } = useAuth();
  const activeMembership = memberships.find((m) => m.tenant_id === activeTenantId) || memberships[0];
  const userRole = activeMembership?.role || "owner";

  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [allowedRoles, setAllowedRoles] = useState<string[]>(["owner", "manager", "member"]);
  const [tagsInput, setTagsInput] = useState("hr, policy");

  // RAG Ask state
  const [query, setQuery] = useState("");
  const [asking, setAsking] = useState(false);
  const [askResult, setAskResult] = useState<AskResult | null>(null);
  const [askError, setAskError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Fetch document list
  const fetchDocuments = async () => {
    if (!session?.access_token || !activeTenantId) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/documents`, {
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId,
        },
      });
      if (res.ok) {
        const data = await res.json();
        setDocuments(data);
      }
    } catch (err) {
      console.error("Failed to load documents:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, [session, activeTenantId]);

  // Handle document upload
  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;
    if (!session?.access_token || !activeTenantId) {
      setUploadError("Please log in to upload documents.");
      return;
    }

    setUploading(true);
    setUploadError(null);

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("allowed_roles", JSON.stringify(allowedRoles));
    const parsedTags = tagsInput
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    formData.append("tags", JSON.stringify(parsedTags));

    try {
      const res = await fetch(`${API_BASE}/api/v1/documents`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId,
        },
        body: formData,
      });

      if (res.ok) {
        setSelectedFile(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
        await fetchDocuments();
      } else {
        const err = await res.json();
        setUploadError(err?.detail || "Upload failed");
      }
    } catch (err: any) {
      setUploadError(err.message || "Failed to connect to storage service");
    } finally {
      setUploading(false);
    }
  };

  // Handle document delete
  const handleDeleteDocument = async (id: string) => {
    if (!session?.access_token || !activeTenantId) return;
    if (!confirm("Are you sure you want to delete this document and remove its indexed vectors?")) {
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/v1/documents/${id}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId,
        },
      });
      if (res.ok) {
        setDocuments((prev) => prev.filter((d) => d.id !== id));
      }
    } catch (err) {
      console.error("Failed to delete document:", err);
    }
  };

  // Handle RAG Ask Knowledge
  const handleAskKnowledge = async (e?: React.FormEvent, customQuery?: string) => {
    if (e) e.preventDefault();
    const q = customQuery || query;
    if (!q.trim()) return;
    if (!session?.access_token || !activeTenantId) {
      setAskError("Please log in to ask questions.");
      return;
    }

    setAsking(true);
    setAskError(null);
    setAskResult(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/knowledge/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId,
        },
        body: JSON.stringify({ query: q, top_k: 5 }),
      });

      if (res.ok) {
        const data: AskResult = await res.json();
        setAskResult(data);
      } else {
        const err = await res.json();
        setAskError(err?.detail || "Knowledge retrieval failed");
      }
    } catch (err: any) {
      setAskError(err.message || "Failed to query knowledge agent");
    } finally {
      setAsking(false);
    }
  };

  const toggleRole = (role: string) => {
    setAllowedRoles((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]
    );
  };

  return (
    <div className="space-y-8 max-w-6xl">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-[24px] font-medium text-foreground tracking-tight">Knowledge Base</h1>
          <p className="text-[14px] text-muted-foreground mt-1">
            Upload, chunk, and index corporate policies and manuals for autonomous employee RAG.
          </p>
        </div>
        <button
          onClick={fetchDocuments}
          className="h-9 px-3 border border-border rounded-md text-[13px] font-medium hover:bg-muted transition-colors inline-flex items-center gap-2 self-start md:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* RAG Knowledge Assistant Card */}
      <div className="p-6 border border-border rounded-lg bg-card space-y-4">
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-foreground" />
          <h2 className="text-[16px] font-medium text-foreground">
            Ask Knowledge Assistant (RAG)
          </h2>
        </div>

        <form onSubmit={(e) => handleAskKnowledge(e)} className="space-y-3">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-3 text-muted-foreground" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask any question over uploaded company policies..."
                className="w-full pl-9 pr-3.5 py-2 rounded-md border border-border bg-background text-[14px] text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
            <button
              type="submit"
              disabled={asking || !query.trim()}
              className="h-9 px-4 rounded-md bg-primary text-primary-foreground text-[14px] font-medium hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center gap-2 whitespace-nowrap"
            >
              <Sparkles className="w-3.5 h-3.5" />
              {asking ? "Retrieving..." : "Ask assistant"}
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[12px] text-muted-foreground mr-1">Suggested questions:</span>
            {QUICK_QUESTIONS.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => {
                  setQuery(q);
                  handleAskKnowledge(undefined, q);
                }}
                className="px-2.5 py-1 text-[12px] rounded border border-border bg-muted/40 hover:bg-muted text-foreground transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </form>

        {askError && (
          <div className="text-[13px] text-foreground bg-muted p-2.5 rounded border border-border flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            <span>{askError}</span>
          </div>
        )}

        {/* Answer Output with Citations */}
        {askResult && (
          <div className="p-4 rounded-md border border-border bg-background space-y-3 mt-4">
            <div className="flex items-center justify-between border-b border-border pb-2">
              <span className="text-[12px] font-medium text-foreground">
                Answer from Knowledge Base ({askResult.chunks_used} sources used)
              </span>
              <div className="flex flex-wrap gap-1.5">
                {askResult.citations.map((cite, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded text-[11px] font-mono bg-muted border border-border text-foreground"
                  >
                    {cite}
                  </span>
                ))}
              </div>
            </div>

            <p className="text-[13px] text-foreground leading-relaxed whitespace-pre-wrap">
              {askResult.answer}
            </p>

            {askResult.sources?.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-border">
                <span className="text-[11px] font-mono text-muted-foreground uppercase tracking-wider">
                  Retrieved Context Snippets:
                </span>
                <div className="space-y-1.5">
                  {askResult.sources.map((s, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded bg-muted/40 border border-border text-[12px] font-mono space-y-1"
                    >
                      <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                        <span className="font-bold text-foreground">{s.citation}</span>
                        <span>Score: {s.score}</span>
                      </div>
                      <p className="text-foreground/90 font-sans">{s.text_snippet}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Upload Document Section */}
      <div className="p-6 border border-border rounded-lg bg-card space-y-4">
        <div className="flex items-center gap-2">
          <Upload className="w-4 h-4 text-foreground" />
          <h2 className="text-[16px] font-medium text-foreground">Upload and Index Document</h2>
        </div>

        <form onSubmit={handleUpload} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-[13px] font-medium text-foreground">File (PDF, DOCX, TXT, MD)</label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.doc,.txt,.md,.json,.csv"
                onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                className="w-full px-3 py-1.5 text-[13px] rounded-md border border-border bg-background text-foreground file:mr-3 file:py-1 file:px-2.5 file:rounded file:border-0 file:text-[12px] file:bg-muted file:text-foreground cursor-pointer"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[13px] font-medium text-foreground">Tags (comma-separated)</label>
              <input
                type="text"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                placeholder="hr, policy, engineering"
                className="w-full px-3 py-2 rounded-md border border-border bg-background text-[13px] text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-[13px] font-medium text-foreground">
              Allowed Roles (Role-based access filtering)
            </label>
            <div className="flex flex-wrap gap-2">
              {["owner", "manager", "approver", "member", "auditor"].map((role) => {
                const isSelected = allowedRoles.includes(role);
                return (
                  <button
                    key={role}
                    type="button"
                    onClick={() => toggleRole(role)}
                    className={`px-3 py-1 rounded text-[12px] font-mono border capitalize transition-colors ${
                      isSelected
                        ? "bg-primary text-primary-foreground border-primary"
                        : "bg-muted/40 text-muted-foreground border-border hover:bg-muted"
                    }`}
                  >
                    {role}
                  </button>
                );
              })}
            </div>
          </div>

          {uploadError && (
            <div className="text-[13px] text-foreground bg-muted p-2.5 rounded border border-border flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              <span>{uploadError}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={uploading || !selectedFile}
            className="h-9 px-4 rounded-md bg-primary text-primary-foreground text-[14px] font-medium hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center gap-2"
          >
            <Upload className="w-3.5 h-3.5" />
            {uploading ? "Ingesting & Chunking..." : "Upload document"}
          </button>
        </form>
      </div>

      {/* Document Library Table */}
      <div className="border border-border rounded-lg bg-card overflow-hidden">
        <div className="px-4 py-3 border-b border-border bg-muted/40 flex items-center justify-between">
          <span className="text-[14px] font-medium text-foreground">Document Library</span>
          <span className="text-[12px] text-muted-foreground">
            {documents.length} {documents.length === 1 ? "document" : "documents"} indexed
          </span>
        </div>

        {loading && documents.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground text-[14px]">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" />
            Loading documents...
          </div>
        ) : documents.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <FileText className="w-8 h-8 text-muted-foreground mx-auto stroke-[1.5]" />
            <p className="text-[14px] text-foreground font-medium">No documents uploaded yet</p>
            <p className="text-[13px] text-muted-foreground max-w-sm mx-auto">
              Upload company policy files or employee handbooks above to enable automated agent retrieval.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-border bg-muted/20 text-muted-foreground font-medium">
                  <th className="py-3 px-4">Document Name</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Chunks</th>
                  <th className="py-3 px-4">Allowed Roles</th>
                  <th className="py-3 px-4">Tags</th>
                  <th className="py-3 px-4">Uploaded</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-muted/10 transition-colors">
                    <td className="py-3 px-4 font-medium text-foreground flex items-center gap-2">
                      <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                      <span className="truncate max-w-xs">{doc.name}</span>
                    </td>
                    <td className="py-3 px-4">
                      {doc.status === "ready" ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[12px] font-medium bg-muted text-foreground border border-border">
                          <CheckCircle2 className="w-3 h-3" /> Ready
                        </span>
                      ) : doc.status === "failed" ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[12px] font-medium bg-muted text-foreground border border-border">
                          <AlertCircle className="w-3 h-3" /> Failed
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[12px] font-medium bg-muted text-foreground border border-border">
                          <RefreshCw className="w-3 h-3 animate-spin" /> Processing
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono text-[12px]">{doc.chunk_count} chunks</td>
                    <td className="py-3 px-4">
                      <div className="flex flex-wrap gap-1 max-w-xs">
                        {doc.allowed_roles.map((r) => (
                          <span
                            key={r}
                            className="px-1.5 py-0.5 text-[11px] rounded bg-muted text-foreground border border-border font-mono capitalize"
                          >
                            {r}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex flex-wrap gap-1">
                        {doc.tags?.length > 0 ? (
                          doc.tags.map((t) => (
                            <span
                              key={t}
                              className="px-1.5 py-0.5 text-[11px] rounded border border-border text-muted-foreground font-mono"
                            >
                              #{t}
                            </span>
                          ))
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-muted-foreground whitespace-nowrap">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => handleDeleteDocument(doc.id)}
                        className="p-1 text-muted-foreground hover:text-foreground transition-colors"
                        title="Delete document and purge vectors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
