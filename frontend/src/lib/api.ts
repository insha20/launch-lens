// lib/api.ts — typed fetch wrapper for the LaunchLens backend

import { LaunchLensReport } from "@/types/pipeline";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/**
 * Run the full 5-agent pipeline.
 * Returns the complete LaunchLensReport.
 * Runtime: 30-90 seconds normally; up to 5+ minutes when rate-limited.
 */
export async function runPipeline(
  description: string,
  onStageChange?: (stage: string) => void,
  onElapsed?: (seconds: number) => void
): Promise<LaunchLensReport> {
  const stages = [
    { label: "analyzing",    delay: 0 },
    { label: "researching",  delay: 4000 },
    { label: "synthesizing", delay: 18000 },
    { label: "scoring",      delay: 28000 },
    { label: "writing",      delay: 36000 },
    // After 45s the backend may be waiting for Gemini rate-limit reset
    { label: "retrying",     delay: 45000 },
  ];

  const timers: ReturnType<typeof setTimeout>[] = [];
  let elapsed = 0;

  if (onStageChange) {
    stages.forEach(({ label, delay }) => {
      timers.push(setTimeout(() => onStageChange(label), delay));
    });
  }

  // Tick elapsed seconds so the UI can show "waiting Xs..."
  const ticker = onElapsed
    ? setInterval(() => { elapsed += 1; onElapsed(elapsed); }, 1000)
    : null;

  try {
    const res = await fetch(`${API_BASE}/launch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description }),
    });

    if (!res.ok) {
      const text = await res.text();
      throw new ApiError(res.status, text);
    }

    return (await res.json()) as LaunchLensReport;
  } finally {
    timers.forEach((t) => clearTimeout(t));
    if (ticker) clearInterval(ticker);
  }
}
