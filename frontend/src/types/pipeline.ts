// types/pipeline.ts — mirrors backend schemas.py exactly

export interface ICPHypothesis {
  persona: string;
  pain_intensity: number;
  why_they_pay: string;
  communities: string[];
  search_queries: string[];
}

export interface ProductAnalysis {
  problem_being_solved: string;
  assumed_customer: string;
  market_category: string;
  icp_hypotheses: ICPHypothesis[];
  red_flags: string[];
}

export interface SynthesisResult {
  hypothesis_persona: string;
  supporting_quotes: string[];
  pain_confirmed: boolean;
  confidence_score: number;
}

export interface PMFScore {
  score: number;           // 1-10
  reasoning: string;
  strongest_signal: string;
  biggest_gap: string;
  verdict: string;         // "strong signal" | "moderate signal" | "weak signal" | "insufficient data"
}

export interface GTMPack {
  target_persona: string;
  cold_dm: string;
  reddit_post_angle: string;
  landing_page_headline: string;
  landing_page_subheadline: string;
  community_targets: string[];
}

export interface LaunchLensReport {
  product_analysis: ProductAnalysis;
  pmf_score: PMFScore | null;
  gtm_pack: GTMPack | null;
  pipeline_status: "complete" | "insufficient_data" | "error" | "running";
  error_message: string | null;
}

// UI state for streaming progress
export type PipelineStage =
  | "idle"
  | "analyzing"
  | "researching"
  | "synthesizing"
  | "scoring"
  | "writing"
  | "retrying"
  | "done"
  | "error";
