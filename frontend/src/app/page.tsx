"use client";
import { useState } from "react";
import { runPipeline, ApiError } from "@/lib/api";
import { LaunchLensReport, PipelineStage } from "@/types/pipeline";
import PipelineProgress from "@/components/PipelineProgress";
import ReportView from "@/components/ReportView";

const STAGE_LABELS: Record<string, string> = {
  idle: "Ready",
  analyzing: "Analyzing your product...",
  researching: "Searching Reddit + Hacker News...",
  synthesizing: "Embedding posts into Chroma...",
  scoring: "Scoring product-market fit...",
  writing: "Writing GTM copy...",
  retrying: "Waiting for Gemini API...",
  done: "Done",
  error: "Something went wrong",
};

const PLACEHOLDER = `e.g. A Notion-based CRM for freelancers that automatically reminds you to follow up on proposals and tracks deal stages visually.`;

function formatElapsed(s: number) {
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

export default function Home() {
  const [description, setDescription] = useState("");
  const [stage, setStage] = useState<PipelineStage>("idle");
  const [report, setReport] = useState<LaunchLensReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);

  const isRunning = stage !== "idle" && stage !== "done" && stage !== "error";
  const isRetrying = stage === "retrying";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!description.trim() || isRunning) return;
    setReport(null);
    setError(null);
    setElapsed(0);
    setStage("analyzing");
    try {
      const result = await runPipeline(
        description.trim(),
        (s) => setStage(s as PipelineStage),
        (s) => setElapsed(s)
      );
      setStage("done");
      setReport(result);
    } catch (err) {
      setStage("error");
      const raw = err instanceof ApiError ? err.message : String(err);
      // Strip the verbose JSON — extract the detail string if present
      try {
        const parsed = JSON.parse(raw);
        setError(parsed.detail ?? raw);
      } catch {
        setError(raw);
      }
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans">
      {/* Header */}
      <header className="border-b border-zinc-800 px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center gap-3">
          <span className="text-2xl">🔭</span>
          <div>
            <h1 className="text-lg font-bold tracking-tight">LaunchLens</h1>
            <p className="text-xs text-zinc-400">AI-powered product-market fit validator</p>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-12 space-y-10">
        {/* Input form */}
        <section>
          <h2 className="text-2xl font-semibold mb-2">Validate your idea</h2>
          <p className="text-zinc-400 mb-6 text-sm">
            Describe your product and our 5-agent pipeline will search Reddit &amp; Hacker News,
            score PMF, and generate GTM copy — all in one run.
          </p>
          <form onSubmit={handleSubmit} className="space-y-4">
            <textarea
              className="w-full rounded-lg bg-zinc-900 border border-zinc-700 text-zinc-100
                         placeholder-zinc-500 px-4 py-3 text-sm resize-none focus:outline-none
                         focus:ring-2 focus:ring-indigo-500 transition"
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={PLACEHOLDER}
              disabled={isRunning}
            />
            <button
              type="submit"
              disabled={!description.trim() || isRunning}
              className="px-6 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40
                         disabled:cursor-not-allowed text-sm font-semibold transition"
            >
              {isRunning ? STAGE_LABELS[stage] : "Run pipeline →"}
            </button>
          </form>
        </section>

        {/* Pipeline progress */}
        {stage !== "idle" && (
          <section>
            <PipelineProgress stage={stage} />
          </section>
        )}

        {/* Rate-limit / retrying banner */}
        {isRetrying && (
          <div className="rounded-lg border border-yellow-700 bg-yellow-950/50 px-4 py-3 text-sm text-yellow-300 space-y-1">
            <p className="font-semibold">⏳ Gemini API rate limit reached — retrying automatically</p>
            <p className="text-yellow-400/80">
              The free tier allows 20 requests/day. The backend is waiting for the retry window and will
              resume without any action needed. Elapsed: <span className="font-mono">{formatElapsed(elapsed)}</span>
            </p>
          </div>
        )}

        {/* Elapsed time when running (non-retrying) */}
        {isRunning && !isRetrying && elapsed > 10 && (
          <p className="text-xs text-zinc-500 text-center">Running for {formatElapsed(elapsed)}…</p>
        )}

        {/* Error */}
        {stage === "error" && error && (
          <div className="rounded-lg border border-red-700 bg-red-950 px-4 py-3 text-sm text-red-300">
            <span className="font-semibold">Error: </span>{error}
          </div>
        )}

        {/* Report */}
        {report && stage === "done" && (
          <section>
            <ReportView report={report} />
          </section>
        )}
      </main>
    </div>
  );
}
