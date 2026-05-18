// components/ReportView.tsx
"use client";

import { useState } from "react";
import { LaunchLensReport } from "@/types/pipeline";

interface Props {
  report: LaunchLensReport;
}

/* ─── helpers ──────────────────────────────────────────────────── */

function scoreColor(score: number) {
  if (score >= 7) return { ring: "ring-green-500", text: "text-green-400", bg: "bg-green-500/10" };
  if (score >= 5) return { ring: "ring-yellow-500", text: "text-yellow-400", bg: "bg-yellow-500/10" };
  return { ring: "ring-red-500", text: "text-red-400", bg: "bg-red-500/10" };
}

const VERDICT_LABEL: Record<string, string> = {
  "strong signal":      "✅ Strong demand confirmed — good time to build",
  "moderate signal":    "🟡 Some demand found — validate further before scaling",
  "weak signal":        "🔴 Weak demand — the problem may not be urgent enough",
  "insufficient data":  "⚪ Not enough data — try a more specific description",
};

function useCopy(text: string) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }
  return { copy, copied };
}

/* ─── sub-components ───────────────────────────────────────────── */

function CopyButton({ text }: { text: string }) {
  const { copy, copied } = useCopy(text);
  return (
    <button
      onClick={copy}
      className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border transition
        ${copied
          ? "bg-green-500/10 border-green-500/30 text-green-400"
          : "bg-zinc-800 border-zinc-700 text-zinc-400 hover:text-zinc-200 hover:border-zinc-600"
        }`}
    >
      {copied ? (
        <>
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
          </svg>
          Copied!
        </>
      ) : (
        <>
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          Copy
        </>
      )}
    </button>
  );
}

function CopyBlock({ label, description, content }: { label: string; description?: string; content: string }) {
  return (
    <div className="space-y-2">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">{label}</p>
          {description && <p className="text-[11px] text-zinc-500 mt-0.5">{description}</p>}
        </div>
        <CopyButton text={content} />
      </div>
      <div className="bg-zinc-900 border border-zinc-700/60 rounded-xl p-4">
        <p className="text-sm text-zinc-300 whitespace-pre-wrap leading-relaxed">{content}</p>
      </div>
    </div>
  );
}

/* ─── TABS ──────────────────────────────────────────────────────── */
type Tab = "overview" | "audience" | "copy";

const TABS: { id: Tab; label: string; emoji: string }[] = [
  { id: "overview",  label: "Overview",     emoji: "📊" },
  { id: "audience",  label: "Audience",     emoji: "👥" },
  { id: "copy",      label: "Launch Copy",  emoji: "🚀" },
];

/* ─── MAIN COMPONENT ────────────────────────────────────────────── */

export default function ReportView({ report }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [redFlagsOpen, setRedFlagsOpen] = useState(false);

  const { product_analysis, pmf_score, gtm_pack, pipeline_status, error_message } = report;

  if (pipeline_status === "error") {
    return (
      <div className="border border-red-700/40 bg-red-950/30 rounded-2xl p-6 space-y-2 max-w-2xl mx-auto">
        <p className="text-sm font-semibold text-red-300">Pipeline error</p>
        <p className="text-sm text-red-400/80">{error_message}</p>
      </div>
    );
  }

  const colors = pmf_score ? scoreColor(pmf_score.score) : scoreColor(0);
  const verdictLabel = pmf_score ? (VERDICT_LABEL[pmf_score.verdict.toLowerCase()] ?? pmf_score.verdict) : "";
  const redFlagCount = product_analysis?.red_flags.length ?? 0;

  return (
    <div className="w-full max-w-3xl mx-auto space-y-6 pb-20">

      {/* ── Score Hero ── */}
      {pmf_score && (
        <div className={`rounded-2xl border ${colors.ring} border-opacity-30 ${colors.bg} p-6 sm:p-8`}>
          <div className="flex flex-col sm:flex-row sm:items-center gap-6">
            {/* Big score circle */}
            <div className={`flex-shrink-0 w-24 h-24 rounded-full ring-4 ${colors.ring} ${colors.bg} flex flex-col items-center justify-center mx-auto sm:mx-0`}>
              <span className={`text-4xl font-black ${colors.text}`}>{pmf_score.score}</span>
              <span className="text-xs text-zinc-500 font-medium">/10</span>
            </div>

            <div className="flex-1 text-center sm:text-left space-y-2">
              <p className="text-base font-semibold text-zinc-100">Market Fit Score</p>
              <p className="text-sm font-medium text-zinc-300">{verdictLabel}</p>
              <p className="text-sm text-zinc-400 leading-relaxed">{pmf_score.reasoning}</p>
            </div>
          </div>

          {/* Signal / Gap cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-6">
            <div className="bg-green-500/5 border border-green-500/20 rounded-xl p-4 space-y-1">
              <p className="text-xs font-semibold text-green-400 uppercase tracking-wider flex items-center gap-1.5">
                <span>💪</span> Strongest Signal
              </p>
              <p className="text-sm text-zinc-300 leading-relaxed">
                {pmf_score.strongest_signal || <span className="text-zinc-600 italic">No signal identified</span>}
              </p>
            </div>
            <div className="bg-orange-500/5 border border-orange-500/20 rounded-xl p-4 space-y-1">
              <p className="text-xs font-semibold text-orange-400 uppercase tracking-wider flex items-center gap-1.5">
                <span>⚠️</span> Biggest Gap
              </p>
              <p className="text-sm text-zinc-300 leading-relaxed">
                {pmf_score.biggest_gap || <span className="text-zinc-600 italic">No gap identified</span>}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab bar ── */}
      <div className="flex gap-1 bg-zinc-900 border border-zinc-800 rounded-xl p-1">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-sm font-medium transition
              ${activeTab === tab.id
                ? "bg-zinc-800 text-zinc-100 shadow-sm"
                : "text-zinc-500 hover:text-zinc-300"
              }`}
          >
            <span>{tab.emoji}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* ── Tab: Overview ── */}
      {activeTab === "overview" && product_analysis && (
        <div className="space-y-4">
          {/* Problem statement */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 space-y-2">
            <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Problem being solved</p>
            <p className="text-sm text-zinc-200 leading-relaxed">{product_analysis.problem_being_solved}</p>
            <div className="flex flex-wrap gap-2 pt-1">
              <span className="text-[11px] bg-zinc-800 border border-zinc-700 text-zinc-400 px-2 py-0.5 rounded-full">
                📂 {product_analysis.market_category}
              </span>
              <span className="text-[11px] bg-zinc-800 border border-zinc-700 text-zinc-400 px-2 py-0.5 rounded-full">
                🎯 {product_analysis.assumed_customer}
              </span>
            </div>
          </div>

          {/* Red Flags */}
          {redFlagCount > 0 && (
            <div className="bg-red-950/20 border border-red-700/30 rounded-2xl overflow-hidden">
              <button
                className="w-full flex items-center justify-between px-5 py-4 text-left"
                onClick={() => setRedFlagsOpen((v) => !v)}
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-red-400">⚑ Red Flags</span>
                  <span className="text-xs bg-red-500/20 text-red-400 border border-red-500/20 px-2 py-0.5 rounded-full font-medium">
                    {redFlagCount}
                  </span>
                </div>
                <svg
                  className={`w-4 h-4 text-red-400 transition-transform ${redFlagsOpen ? "rotate-180" : ""}`}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {redFlagsOpen && (
                <div className="px-5 pb-4 space-y-2 border-t border-red-700/20">
                  {product_analysis.red_flags.map((f, i) => (
                    <div key={i} className="flex items-start gap-2.5 pt-2">
                      <span className="text-red-500 flex-shrink-0 mt-0.5">•</span>
                      <p className="text-sm text-zinc-400 leading-relaxed">{f}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Tab: Audience ── */}
      {activeTab === "audience" && product_analysis && (
        <div className="space-y-4">
          <p className="text-xs text-zinc-500 px-1">
            Each persona is a distinct customer hypothesis. The number shows <strong className="text-zinc-400">pain intensity</strong> (1–10).
          </p>
          {product_analysis.icp_hypotheses.map((h, i) => {
            const pain = h.pain_intensity;
            const painColor = pain >= 7 ? "text-red-400 bg-red-500/10 border-red-500/20"
              : pain >= 5 ? "text-yellow-400 bg-yellow-500/10 border-yellow-500/20"
              : "text-zinc-400 bg-zinc-800 border-zinc-700";

            return (
              <div key={i} className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 space-y-3">
                {/* Persona header */}
                <div className="flex items-start gap-3">
                  <div className={`flex-shrink-0 w-9 h-9 rounded-full border flex items-center justify-center text-sm font-bold ${painColor}`}>
                    {pain}
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-zinc-100">{h.persona}</p>
                    <p className="text-xs text-zinc-500 mt-0.5">Pain intensity: {pain}/10</p>
                  </div>
                </div>

                {/* Why they pay */}
                <div className="bg-zinc-800/50 rounded-xl px-4 py-3">
                  <p className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider mb-1">Why they'd pay</p>
                  <p className="text-sm text-zinc-300 leading-relaxed">{h.why_they_pay}</p>
                </div>

                {/* Communities */}
                {h.communities.length > 0 && (
                  <div>
                    <p className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">Where to find them</p>
                    <div className="flex flex-wrap gap-1.5">
                      {h.communities.map((c) => (
                        <span key={c} className="text-xs bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 px-2.5 py-1 rounded-full">
                          {c}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Tab: Launch Copy ── */}
      {activeTab === "copy" && (
        <div className="space-y-5">
          {gtm_pack ? (
            <>
              <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3">
                <span className="text-zinc-500 text-xs">Written for:</span>
                <span className="text-xs font-semibold text-zinc-300">{gtm_pack.target_persona}</span>
              </div>

              {/* Landing page preview */}
              <div className="bg-indigo-950/30 border border-indigo-500/20 rounded-2xl p-6 space-y-2 relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/5 rounded-full -translate-y-8 translate-x-8 pointer-events-none" />
                <p className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wider">Landing Page Headline</p>
                <p className="text-xl sm:text-2xl font-bold text-zinc-100 leading-tight">{gtm_pack.landing_page_headline}</p>
                <p className="text-sm text-zinc-400 leading-relaxed">{gtm_pack.landing_page_subheadline}</p>
                <div className="pt-2">
                  <CopyButton text={`${gtm_pack.landing_page_headline}\n\n${gtm_pack.landing_page_subheadline}`} />
                </div>
              </div>

              <CopyBlock
                label="Cold outreach message"
                description="Personalize [Name] and the opener before sending."
                content={gtm_pack.cold_dm}
              />
              <CopyBlock
                label="Reddit post angle"
                description="Post in one of the community targets below. Be genuine — don't paste verbatim."
                content={gtm_pack.reddit_post_angle}
              />

              {gtm_pack.community_targets.length > 0 && (
                <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5 space-y-2">
                  <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Community targets</p>
                  <div className="flex flex-wrap gap-2">
                    {gtm_pack.community_targets.map((c) => (
                      <span key={c} className="text-xs bg-zinc-800 border border-zinc-700 text-zinc-300 px-3 py-1 rounded-full">
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="border border-yellow-700/30 bg-yellow-950/20 rounded-2xl p-6 space-y-2">
              <p className="text-sm font-semibold text-yellow-300">Launch copy skipped</p>
              <p className="text-sm text-yellow-400/80">
                PMF signal was too weak to generate copy. Collect more community evidence or refine your product description and try again.
              </p>
            </div>
          )}
        </div>
      )}

    </div>
  );
}
