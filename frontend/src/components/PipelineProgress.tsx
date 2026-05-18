// components/PipelineProgress.tsx
"use client";

import { PipelineStage } from "@/types/pipeline";

const STAGES: { key: PipelineStage; label: string; agent: string; emoji: string }[] = [
  { key: "analyzing",    emoji: "🧠", label: "Understanding your product",       agent: "Working out the problem, personas, and market category" },
  { key: "researching",  emoji: "🔍", label: "Searching Reddit & Hacker News",   agent: "Finding real conversations where people complain about this problem" },
  { key: "synthesizing", emoji: "📚", label: "Reading the evidence",             agent: "Matching community posts to each customer hypothesis" },
  { key: "scoring",      emoji: "📊", label: "Scoring market demand",            agent: "How strongly does the evidence confirm real demand?" },
  { key: "writing",      emoji: "✍️",  label: "Writing your launch copy",         agent: "Cold DM, Reddit post, and landing page headline" },
];

const ORDER: PipelineStage[] = STAGES.map((s) => s.key);

interface Props {
  stage: PipelineStage;
  elapsed?: number;
}

function formatElapsed(s: number) {
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

export default function PipelineProgress({ stage, elapsed = 0 }: Props) {
  const displayStage: PipelineStage = stage === "retrying" ? "writing" : stage;
  const currentIndex = ORDER.indexOf(displayStage);
  const completedCount = currentIndex; // stages before current are done

  return (
    <div className="w-full space-y-3">
      {/* Header row */}
      <div className="flex items-center justify-between px-1">
        <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
          Step {Math.min(currentIndex + 1, STAGES.length)} of {STAGES.length}
        </p>
        {elapsed > 0 && (
          <p className="text-xs text-zinc-500 font-mono">{formatElapsed(elapsed)}</p>
        )}
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-indigo-500 rounded-full transition-all duration-700"
          style={{ width: `${(completedCount / STAGES.length) * 100}%` }}
        />
      </div>

      {/* Step list */}
      <div className="space-y-1.5 pt-1">
        {STAGES.map(({ key, label, agent, emoji }, i) => {
          const isDone    = currentIndex > i;
          const isActive  = currentIndex === i;
          const isPending = currentIndex < i;

          return (
            <div
              key={key}
              className={`flex items-center gap-3 rounded-xl px-4 py-3 transition-all duration-300 ${
                isActive
                  ? "bg-indigo-500/10 border border-indigo-500/30"
                  : isDone
                  ? "bg-zinc-900/40 border border-zinc-800/50 opacity-70"
                  : "opacity-25"
              }`}
            >
              {/* Status icon */}
              <div className="flex-shrink-0 w-6 h-6 flex items-center justify-center">
                {isDone ? (
                  <svg className="w-5 h-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                ) : isActive ? (
                  <span className="w-4 h-4 rounded-full border-2 border-indigo-400/40 border-t-indigo-400 animate-spin block" />
                ) : (
                  <span className="text-base">{emoji}</span>
                )}
              </div>

              {/* Text */}
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-semibold ${isActive ? "text-indigo-300" : isDone ? "text-zinc-300" : "text-zinc-400"}`}>
                  {isActive ? <span>{emoji} {label}</span> : label}
                </p>
                {isActive && (
                  <p className="text-xs text-zinc-500 mt-0.5">{agent}</p>
                )}
              </div>

              {isDone && (
                <span className="text-[10px] text-green-500 font-medium flex-shrink-0">Done</span>
              )}
            </div>
          );
        })}
      </div>

      {stage === "retrying" && (
        <div className="rounded-xl border border-yellow-600/30 bg-yellow-950/20 px-4 py-3 space-y-1">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full border-2 border-yellow-400/40 border-t-yellow-400 animate-spin flex-shrink-0" />
            <p className="text-xs font-semibold text-yellow-300">Still working — almost there</p>
          </div>
          <p className="text-xs text-yellow-400/70 leading-relaxed pl-5">
            The AI model is briefly rate-limited and will resume automatically in a moment. Your results are on their way — please keep this tab open.
          </p>
        </div>
      )}
    </div>
  );
}
