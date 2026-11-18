"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import {
  Mic,
  MicOff,
  Square,
  Volume2,
  VolumeX,
  Play,
  RotateCcw,
  Sparkles,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  AlertCircle,
  ArrowRight,
  Radio,
  Clock,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface VoiceEvent {
  event: string;
  timestamp?: string;
  [key: string]: any;
}

interface PendingApproval {
  workflow_id: string;
  action_type: string;
  reason: string;
}

export default function VoicePage() {
  const { session, activeTenantId } = useAuth();

  // Voice session state
  const [mode, setMode] = useState<"push_to_talk" | "continuous">("push_to_talk");
  const [state, setState] = useState<"idle" | "listening" | "processing" | "speaking" | "waiting_approval">("idle");
  const [transcript, setTranscript] = useState<string>("");
  const [spokenReply, setSpokenReply] = useState<string>("");
  const [activeWorkflowId, setActiveWorkflowId] = useState<string | null>(null);
  const [workflowEvents, setWorkflowEvents] = useState<Array<{ type: string; agent?: string; message?: string }>>([]);
  const [pendingApproval, setPendingApproval] = useState<PendingApproval | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [manualInput, setManualInput] = useState("");
  const [submittingManual, setSubmittingManual] = useState(false);

  // Audio recording & playback refs
  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const currentAudioSourceRef = useRef<HTMLAudioElement | null>(null);
  const isRecordingRef = useRef<boolean>(false);

  // Initialize or connect WebSocket
  const connectWebSocket = useCallback(() => {
    if (!session?.access_token || !activeTenantId) return null;

    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = API_BASE.replace(/^https?:\/\//, "");
    const wsUrl = `${wsProtocol}//${host}/api/v1/voice/stream?token=${encodeURIComponent(session.access_token)}&tenant_id=${encodeURIComponent(activeTenantId)}`;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("Voice WebSocket connected.");
      setErrorMsg(null);
    };

    ws.onmessage = async (evt) => {
      if (typeof evt.data === "string") {
        try {
          const data: VoiceEvent = jsonParseSafe(evt.data);
          handleVoiceServerEvent(data);
        } catch (e) {
          console.error("Failed to parse WS JSON:", e);
        }
      } else if (evt.data instanceof Blob) {
        // Binary audio chunk received from server
        playAudioBlob(evt.data);
      }
    };

    ws.onerror = (e) => {
      console.warn("Voice WebSocket warning/error:", e);
    };

    ws.onclose = () => {
      console.log("Voice WebSocket closed.");
    };

    wsRef.current = ws;
    return ws;
  }, [session?.access_token, activeTenantId]);

  function jsonParseSafe(str: string): VoiceEvent {
    return JSON.parse(str);
  }

  // Handle incoming server events
  const handleVoiceServerEvent = (data: VoiceEvent) => {
    switch (data.event) {
      case "session.started":
        setState("listening");
        break;

      case "session.state_change":
        if (data.state) setState(data.state);
        break;

      case "vad.speech_start":
        setState("listening");
        break;

      case "vad.speech_end":
        // In continuous mode, speech end triggers processing
        setState("processing");
        break;

      case "transcript.final":
        if (data.text) {
          setTranscript(data.text);
        }
        break;

      case "workflow.dispatched":
        if (data.workflow_id) {
          setActiveWorkflowId(data.workflow_id);
          setWorkflowEvents([]);
        }
        break;

      case "workflow.event":
        setWorkflowEvents((prev) => [
          ...prev,
          { type: data.type, agent: data.agent, message: data.message },
        ]);
        break;

      case "approval.required":
        setState("waiting_approval");
        setPendingApproval({
          workflow_id: data.workflow_id,
          action_type: data.action_type || "action",
          reason: data.reason || "Action requires manager approval.",
        });
        break;

      case "tts.started":
        if (data.text) {
          setSpokenReply(data.text);
        }
        setState("speaking");
        break;

      case "tts.chunk":
        if (data.data && !isMuted) {
          playBase64AudioChunk(data.data);
        }
        break;

      case "tts.completed":
        if (mode === "continuous") {
          setState("listening");
        } else {
          setState("idle");
        }
        break;

      case "session.interrupted":
        stopAudioPlayback();
        setState(mode === "continuous" ? "listening" : "idle");
        break;

      case "error":
        setErrorMsg(data.message || "An error occurred during voice processing.");
        setState("idle");
        break;

      default:
        break;
    }
  };

  // Audio Playback
  const playAudioBlob = (blob: Blob) => {
    if (isMuted) return;
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    currentAudioSourceRef.current = audio;
    audio.play().catch((err) => console.warn("Audio play blocked:", err));
  };

  const playBase64AudioChunk = (b64: string) => {
    if (isMuted) return;
    try {
      const byteChars = atob(b64);
      const byteNums = new Array(byteChars.length);
      for (let i = 0; i < byteChars.length; i++) {
        byteNums[i] = byteChars.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNums);
      const blob = new Blob([byteArray], { type: "audio/mpeg" });
      playAudioBlob(blob);
    } catch (e) {
      console.error("Failed to decode audio base64 chunk:", e);
    }
  };

  const stopAudioPlayback = () => {
    if (currentAudioSourceRef.current) {
      currentAudioSourceRef.current.pause();
      currentAudioSourceRef.current = null;
    }
  };

  // Microphone stream management
  const startRecording = async () => {
    setErrorMsg(null);
    try {
      stopAudioPlayback();
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      audioStreamRef.current = stream;

      let ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        ws = connectWebSocket();
      }

      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0 && ws && ws.readyState === WebSocket.OPEN) {
          ws.send(e.data);
        }
      };

      recorder.start(250); // Emit chunk every 250ms
      isRecordingRef.current = true;
      setState("listening");

      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "start", mode }));
      }
    } catch (err: any) {
      console.error("Microphone access error:", err);
      setErrorMsg("Microphone permission denied or audio device not found. You can test voice commands using the text prompt below.");
      setState("idle");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecordingRef.current) {
      mediaRecorderRef.current.stop();
      isRecordingRef.current = false;
    }
    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach((track) => track.stop());
      audioStreamRef.current = null;
    }

    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "stop_speech" }));
    }
    setState("processing");
  };

  // Interrupt button handler
  const handleInterrupt = () => {
    stopAudioPlayback();
    if (isRecordingRef.current) {
      stopRecording();
    }
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "interrupt" }));
    }
    setState(mode === "continuous" ? "listening" : "idle");
  };

  // Fallback REST voice command
  const executeDirectVoiceCommand = async (textToRun: string) => {
    if (!textToRun.trim() || !session?.access_token) return;
    setSubmittingManual(true);
    setErrorMsg(null);
    setTranscript(textToRun);
    setSpokenReply("");
    setPendingApproval(null);
    setWorkflowEvents([]);
    setState("processing");

    try {
      const res = await fetch(`${API_BASE}/api/v1/voice/command`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "X-Tenant-ID": activeTenantId || "",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text: textToRun.trim() }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.error?.message || err?.detail || `Error ${res.status}`);
      }

      const data = await res.json();
      setActiveWorkflowId(data.workflow_id);
      setSpokenReply(data.spoken_response);

      if (data.approval_required) {
        setState("waiting_approval");
        setPendingApproval({
          workflow_id: data.workflow_id,
          action_type: data.approval_data?.action_type || "action",
          reason: data.approval_data?.reason || "Action requires approval.",
        });
      } else {
        setState("idle");
      }

      if (data.audio_base64 && !isMuted) {
        playBase64AudioChunk(data.audio_base64);
      }
    } catch (e: any) {
      setErrorMsg(e.message || "Failed to process voice command");
      setState("idle");
    } finally {
      setSubmittingManual(false);
      setManualInput("");
    }
  };

  // Quick prompt suggestions
  const suggestedCommands = [
    "Rank these candidates for the Python role.",
    "Process this month's vendor invoices against purchase orders.",
    "Generate a monthly operations report and send it to management.",
  ];

  useEffect(() => {
    const ws = connectWebSocket();
    return () => {
      stopAudioPlayback();
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [connectWebSocket]);

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">Voice Interface</h1>
            <span className="text-xs px-2 py-0.5 rounded-full border border-border bg-muted text-muted-foreground font-mono">
              Screen 17
            </span>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Speak natural commands to your AI employees with real-time transcription, live captions, and spoken replies.
          </p>
        </div>

        {/* Mode Selector & Mute Toggle */}
        <div className="flex items-center gap-3">
          <div className="flex rounded-md border border-border p-1 bg-muted/40">
            <button
              onClick={() => {
                setMode("push_to_talk");
                if (state === "listening" && !isRecordingRef.current) setState("idle");
              }}
              className={`px-3 py-1 text-xs rounded-sm transition-colors ${
                mode === "push_to_talk" ? "bg-background text-foreground font-medium shadow-sm" : "text-muted-foreground"
              }`}
            >
              Push-to-Talk
            </button>
            <button
              onClick={() => {
                setMode("continuous");
                startRecording();
              }}
              className={`px-3 py-1 text-xs rounded-sm transition-colors ${
                mode === "continuous" ? "bg-background text-foreground font-medium shadow-sm" : "text-muted-foreground"
              }`}
            >
              Continuous
            </button>
          </div>

          <button
            onClick={() => setIsMuted(!isMuted)}
            title={isMuted ? "Unmute Spoken Output" : "Mute Spoken Output"}
            className="p-2 border border-border rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
          >
            {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="p-4 rounded-md border border-border bg-muted/30 flex items-start gap-3">
          <AlertCircle className="w-4 h-4 text-foreground mt-0.5 shrink-0" />
          <div className="text-sm">
            <p className="text-foreground font-medium">Notice</p>
            <p className="text-muted-foreground text-xs mt-0.5">{errorMsg}</p>
          </div>
        </div>
      )}

      {/* Main Interactive Mic Center */}
      <div className="border border-border rounded-lg bg-card p-10 flex flex-col items-center justify-center text-center relative overflow-hidden">
        {/* State Indicator */}
        <div className="mb-6 flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${
              state === "listening"
                ? "bg-foreground animate-ping"
                : state === "processing"
                ? "bg-foreground animate-pulse"
                : state === "speaking"
                ? "bg-foreground"
                : "bg-muted-foreground/40"
            }`}
          />
          <span className="text-xs uppercase tracking-wider text-muted-foreground font-medium">
            {state === "listening" && (mode === "continuous" ? "Listening (VAD Active)..." : "Recording Speech...")}
            {state === "processing" && "Transcribing & Planning..."}
            {state === "speaking" && "Speaking Response..."}
            {state === "waiting_approval" && "Action Requires Approval"}
            {state === "idle" && "Ready to Listen"}
          </span>
        </div>

        {/* Microphone Button */}
        <div className="relative mb-6">
          <button
            onMouseDown={() => {
              if (mode === "push_to_talk") startRecording();
            }}
            onMouseUp={() => {
              if (mode === "push_to_talk") stopRecording();
            }}
            onClick={() => {
              if (mode === "continuous") {
                if (state === "listening") {
                  stopRecording();
                  setState("idle");
                } else {
                  startRecording();
                }
              }
            }}
            className={`w-28 h-28 rounded-full border flex items-center justify-center transition-all ${
              state === "listening"
                ? "bg-foreground text-background border-foreground scale-105 shadow-md"
                : "bg-background text-foreground border-border hover:border-foreground/60 hover:bg-muted/40"
            }`}
          >
            {state === "listening" ? <Mic className="w-10 h-10" /> : <MicOff className="w-10 h-10 opacity-60" />}
          </button>
        </div>

        <p className="text-sm text-foreground font-medium">
          {mode === "push_to_talk" ? "Hold button to speak" : "Continuous listening active"}
        </p>
        <p className="text-xs text-muted-foreground mt-1 max-w-sm">
          {mode === "push_to_talk"
            ? "Release when done. VAD will process your command and synthesize the AI employee's voice reply."
            : "Silence will automatically trigger transcription and execution."}
        </p>

        {/* Interrupt Control Button */}
        <div className="mt-6 flex items-center gap-3">
          <button
            onClick={handleInterrupt}
            className="px-4 py-2 text-xs rounded-md border border-border bg-background hover:bg-muted text-foreground flex items-center gap-2 transition-colors"
          >
            <Square className="w-3.5 h-3.5 fill-current" />
            Interrupt / Stop
          </button>
        </div>
      </div>

      {/* Live Captions & Conversation Display */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Spoken Input Caption */}
        <div className="border border-border rounded-lg p-6 bg-card space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-wider text-muted-foreground font-medium flex items-center gap-1.5">
              <Radio className="w-3.5 h-3.5" /> Spoken Input Caption
            </span>
            {transcript && (
              <span className="text-[11px] text-muted-foreground font-mono">Whisper STT</span>
            )}
          </div>
          <div className="min-h-[100px] flex items-center">
            {transcript ? (
              <p className="text-base text-foreground font-medium leading-relaxed">
                "{transcript}"
              </p>
            ) : (
              <p className="text-xs text-muted-foreground italic">
                Speech transcription will appear here in real time as you speak...
              </p>
            )}
          </div>
        </div>

        {/* AI Spoken Response Card */}
        <div className="border border-border rounded-lg p-6 bg-card space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-wider text-muted-foreground font-medium flex items-center gap-1.5">
              <Volume2 className="w-3.5 h-3.5" /> Spoken AI Reply
            </span>
            {spokenReply && (
              <span className="text-[11px] text-muted-foreground font-mono">Edge-TTS (en-IN)</span>
            )}
          </div>
          <div className="min-h-[100px] flex items-center">
            {spokenReply ? (
              <p className="text-base text-foreground font-medium leading-relaxed">
                "{spokenReply}"
              </p>
            ) : (
              <p className="text-xs text-muted-foreground italic">
                The synthesized voice answer from your AI employee will play and show here...
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Pending Human Approval Card (Screen 17 / Same Approval Path as Text) */}
      {pendingApproval && (
        <div className="border border-border rounded-lg p-6 bg-card space-y-4">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 border border-border rounded-md bg-muted">
                <ShieldAlert className="w-5 h-5 text-foreground" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-foreground">Approval Required</h3>
                <p className="text-xs text-muted-foreground">Action halted by Policy Engine for manager confirmation.</p>
              </div>
            </div>
            <span className="px-2 py-0.5 text-xs rounded-full border border-border bg-muted text-foreground uppercase tracking-wider font-mono">
              {pendingApproval.action_type}
            </span>
          </div>

          <p className="text-sm text-foreground bg-muted/40 p-3 rounded-md border border-border">
            {pendingApproval.reason}
          </p>

          <div className="flex items-center justify-end gap-3 pt-2">
            <Link
              href="/approvals"
              className="text-xs px-4 py-2 rounded-md border border-border hover:bg-muted text-foreground flex items-center gap-2"
            >
              Open Approval Center <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        </div>
      )}

      {/* Live Workflow Timeline Events */}
      {workflowEvents.length > 0 && (
        <div className="border border-border rounded-lg p-6 bg-card space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-foreground flex items-center gap-2">
              <Sparkles className="w-4 h-4" /> Live Orchestrator Execution
            </h3>
            {activeWorkflowId && (
              <Link
                href={`/workflows/${activeWorkflowId}`}
                className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 font-mono"
              >
                View Full Trace <ArrowRight className="w-3 h-3" />
              </Link>
            )}
          </div>

          <div className="space-y-2">
            {workflowEvents.map((evt, idx) => (
              <div
                key={idx}
                className="flex items-start gap-3 p-2.5 rounded-md border border-border/60 bg-muted/20 text-xs"
              >
                <Clock className="w-3.5 h-3.5 text-muted-foreground mt-0.5 shrink-0" />
                <div className="flex-1">
                  <span className="font-semibold text-foreground mr-2 font-mono">
                    [{evt.agent || "system"}]
                  </span>
                  <span className="text-muted-foreground">{evt.message || evt.type}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick Testing: Direct Prompt Input */}
      <div className="border border-border rounded-lg p-6 bg-card space-y-4">
        <h3 className="text-sm font-medium text-foreground">Suggested Spoken Commands</h3>
        <p className="text-xs text-muted-foreground">
          Click any command to execute it through the voice pipeline:
        </p>
        <div className="flex flex-wrap gap-2">
          {suggestedCommands.map((cmd) => (
            <button
              key={cmd}
              onClick={() => executeDirectVoiceCommand(cmd)}
              disabled={submittingManual}
              className="text-xs px-3 py-2 rounded-md border border-border bg-background hover:bg-muted text-foreground text-left transition-colors"
            >
              "{cmd}"
            </button>
          ))}
        </div>

        <div className="pt-2 flex gap-2">
          <input
            type="text"
            value={manualInput}
            onChange={(e) => setManualInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && manualInput.trim()) {
                executeDirectVoiceCommand(manualInput);
              }
            }}
            placeholder="Type a command to test voice pipeline..."
            className="flex-1 px-3 py-2 rounded-md border border-border bg-background text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-foreground"
          />
          <button
            onClick={() => executeDirectVoiceCommand(manualInput)}
            disabled={submittingManual || !manualInput.trim()}
            className="px-4 py-2 rounded-md bg-foreground text-background text-xs font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {submittingManual ? "Running..." : "Run"}
          </button>
        </div>
      </div>
    </div>
  );
}

