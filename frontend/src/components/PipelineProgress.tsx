// components/PipelineProgress.tsx
// Shows which agent is currently running with animated indicator

"use client";

import { PipelineStage } from "@/types/pipeline";

const STAGES: { key: PipelineStage; label: string; agent: string }[] = [
  { key: "analyzing",   label: "Analyzing product",        agent: "Product Analyst" },
  { key: "researching", label: "Searching Reddit + HN",    agent: "Community Researcher" },
  { key: "synthesizing",label: "Embedding into Chroma",    agent: "RAG Synthesizer" },
  { key: "scoring",     label: "Scoring PMF",              agent: "PMF Scorer" },
  { key: "writing",     label: "Writing GTM copy",         agent: "GTM Copywriter" },
];

const ORDER: PipelineStage[] = STAGES.map((s) => s.key);

interface Props {
  stage: PipelineStage;
}

export default function PipelineProgress({ stage }: Props) {
  // 'retrying' is not a pipeline step — keep the last real step (writing) highlighted
  const displayStage: PipelineStage = stage === "retrying" ? "writing" : stage;
  const currentIndex = ORDER.indexOf(displayStage);

  return (
    <div className="w-full max-w-xl mx-auto space-y-2 py-6">
      {STAGES.map(({ key, label, agent }, i) => {
        const isDone    = currentIndex > i;
        const isActive  = currentIndex === i;
        const isPending = currentIndex < i;

        return (
          <div
            key={key}
            className={`flex items-center gap-3 rounded-lg px-4 py-3 transition-all duration-300 ${
              isActive  ? "bg-indigo-50 border border-indigo-200" :
              isDone    ? "opacity-60" :
              "opacity-30"
            }`}
          >
            {/* Status dot */}
            <div className="flex-shrink-0 w-5 h-5 flex items-center justify-center">
              {isDone ? (
                <svg className="w-5 h-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : isActive ? (
                <span className="w-3 h-3 rounded-full bg-indigo-500 animate-pulse block" />
              ) : (
                <span className="w-3 h-3 rounded-full bg-gray-300 block" />
              )}
            </div>

            {/* Label */}
            <div className="flex-1 min-w-0">
              <p className={`text-sm font-medium ${isActive ? "text-indigo-700" : "text-gray-700"}`}>
                {label}
              </p>
              <p className="text-xs text-gray-400">{agent}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
