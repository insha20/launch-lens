"use client";
import { useState } from "react";
import { runPipeline, ApiError } from "@/lib/api";
import { LaunchLensReport, PipelineStage } from "@/types/pipeline";
import PipelineProgress from "@/components/PipelineProgress";
import ReportView from "@/components/ReportView";

const EXAMPLES = [
  "A Notion-based CRM for freelancers that automatically reminds you to follow up on proposals and tracks deal stages visually.",
  "An AI resume builder that tailors your resume to each job description to pass ATS systems and land more interviews.",
  "A sleep-tracking app for parents of newborns that predicts the baby's next sleep window based on patterns.",
];

const HOW_IT_WORKS = [
  { icon: "✍️", step: "Describe your idea", detail: "Paste a product description — one sentence to a paragraph." },
  { icon: "🔍", step: "We search the internet", detail: "5 AI agents scan Reddit & Hacker News for real complaints and demand signals." },
  { icon: "📊", step: "Get your PMF score", detail: "See how strongly the market wants your idea, who it's for, and why." },
  { icon: "🚀", step: "Launch-ready copy", detail: "Walk away with a headline, cold DM, and Reddit post — written in your customers' words." },
];

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
  const showReport = report && stage === "done";

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
      try {
        const parsed = JSON.parse(raw);
        setError(parsed.detail ?? raw);
      } catch {
        setError(raw);
      }
    }
  }

  function handleReset() {
    setStage("idle");
    setReport(null);
    setError(null);
    setDescription("");
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans">
      {/* Header */}
      <header className="border-b border-zinc-800/60 px-6 py-4 sticky top-0 z-20 bg-zinc-950/90 backdrop-blur">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xl">🔭</span>
            <div>
              <h1 className="text-base font-bold tracking-tight">LaunchLens</h1>
              <p className="text-[11px] text-zinc-500 leading-none">AI product-market fit validator</p>
            </div>
          </div>
          {showReport && (
            <button
              onClick={handleReset}
              className="text-xs text-zinc-400 hover:text-zinc-100 border border-zinc-700 hover:border-zinc-500 px-3 py-1.5 rounded-lg transition"
            >
              ← Validate another idea
            </button>
          )}
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6">

        {/* ── Hero + Input (hidden once report is ready) ── */}
        {!showReport && (
          <section className="py-12 sm:py-16 space-y-10">

            {/* Hero copy */}
            {stage === "idle" && (
              <div className="text-center space-y-4 max-w-2xl mx-auto">
                <div className="inline-flex items-center gap-2 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-medium px-3 py-1 rounded-full">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse inline-block" />
                  Powered by 5 AI agents + live community data
                </div>
                <h2 className="text-3xl sm:text-4xl font-bold tracking-tight leading-tight">
                  Does the market actually<br />
                  <span className="text-indigo-400">want what you're building?</span>
                </h2>
                <p className="text-zinc-400 text-base leading-relaxed">
                  Paste your idea and get a PMF score, audience breakdown, and ready-to-use launch copy —
                  backed by real Reddit &amp; Hacker News conversations.
                </p>
              </div>
            )}

            {/* Input card */}
            <div className="max-w-2xl mx-auto">
              <form onSubmit={handleSubmit} className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 space-y-4 shadow-xl">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                    Your product idea
                  </label>
                  <textarea
                    className="w-full rounded-xl bg-zinc-800 border border-zinc-700 text-zinc-100
                               placeholder-zinc-500 px-4 py-3 text-sm resize-none focus:outline-none
                               focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
                    rows={4}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Describe your product in 1–3 sentences. What does it do, for whom, and what problem does it solve?"
                    disabled={isRunning}
                  />
                  <div className="flex items-center justify-between pt-0.5">
                    <p className="text-[11px] text-zinc-600">Tip: more detail = better results</p>
                    <span className={`text-[11px] ${description.length > 600 ? "text-red-400" : "text-zinc-600"}`}>
                      {description.length}/600
                    </span>
                  </div>
                </div>

                {/* Example prompts */}
                {stage === "idle" && !description && (
                  <div className="space-y-1.5">
                    <p className="text-[11px] text-zinc-500 uppercase tracking-wider font-medium">Try an example</p>
                    <div className="flex flex-col gap-1.5">
                      {EXAMPLES.map((ex, i) => (
                        <button
                          key={i}
                          type="button"
                          onClick={() => setDescription(ex)}
                          className="text-left text-xs text-zinc-400 hover:text-zinc-200 bg-zinc-800/50 hover:bg-zinc-800 border border-zinc-700/50 hover:border-zinc-600 rounded-lg px-3 py-2 transition line-clamp-1"
                        >
                          {ex}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={!description.trim() || isRunning || description.length > 600}
                  className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40
                             disabled:cursor-not-allowed text-sm font-semibold transition flex items-center justify-center gap-2"
                >
                  {isRunning ? (
                    <>
                      <span className="w-3.5 h-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                      Analyzing…
                    </>
                  ) : (
                    "Validate my idea →"
                  )}
                </button>
              </form>
            </div>

            {/* Pipeline progress */}
            {isRunning && (
              <div className="max-w-2xl mx-auto space-y-4">
                <PipelineProgress stage={stage} elapsed={elapsed} />
              </div>
            )}

            {/* Error */}
            {stage === "error" && error && (
              <div className="max-w-2xl mx-auto rounded-xl border border-red-700/60 bg-red-950/40 px-5 py-4 space-y-2">
                <p className="text-sm font-semibold text-red-300">
                  {error.includes("quick succession") ? "⏳ Slow down a little" : "Something went wrong"}
                </p>
                <p className="text-xs text-red-400/90">{error}</p>
                <button
                  onClick={handleReset}
                  className="text-xs text-red-400 hover:text-red-200 underline underline-offset-2 transition"
                >
                  Try again
                </button>
              </div>
            )}

            {/* How it works — only on idle */}
            {stage === "idle" && (
              <div className="max-w-2xl mx-auto pt-4">
                <p className="text-xs text-zinc-500 uppercase tracking-wider font-semibold text-center mb-5">How it works</p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {HOW_IT_WORKS.map(({ icon, step, detail }) => (
                    <div key={step} className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-3 text-center space-y-1.5">
                      <div className="text-xl">{icon}</div>
                      <p className="text-xs font-semibold text-zinc-200">{step}</p>
                      <p className="text-[11px] text-zinc-500 leading-relaxed">{detail}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        {/* ── Report ── */}
        {showReport && (
          <section className="py-8">
            <ReportView report={report} />
          </section>
        )}

      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800/50 mt-16 py-6 text-center text-xs text-zinc-600">
        LaunchLens · Validate before you build
      </footer>
    </div>
  );
}
