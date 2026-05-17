// components/ReportView.tsx
// Renders the full LaunchLensReport returned by the pipeline

"use client";

import { LaunchLensReport } from "@/types/pipeline";

interface Props {
  report: LaunchLensReport;
}

function ScoreBadge({ score, verdict }: { score: number; verdict: string }) {
  const color =
    score >= 7 ? "bg-green-100 text-green-800 border-green-200" :
    score >= 5 ? "bg-yellow-100 text-yellow-800 border-yellow-200" :
                 "bg-red-100 text-red-800 border-red-200";

  return (
    <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full border text-sm font-medium ${color}`}>
      <span className="text-2xl font-bold">{score}</span>
      <span className="text-xs opacity-75">/10</span>
      <span className="ml-1 capitalize">{verdict}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-gray-200 rounded-xl p-5 space-y-3">
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">{title}</h3>
      {children}
    </div>
  );
}

function CopyBlock({ label, content }: { label: string; content: string }) {
  function copy() {
    navigator.clipboard.writeText(content);
  }
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</span>
        <button
          onClick={copy}
          className="text-xs text-indigo-500 hover:text-indigo-700 transition-colors"
        >
          Copy
        </button>
      </div>
      <p className="text-sm text-gray-700 bg-gray-50 rounded-lg p-3 whitespace-pre-wrap leading-relaxed">
        {content}
      </p>
    </div>
  );
}

export default function ReportView({ report }: Props) {
  const { product_analysis, pmf_score, gtm_pack, pipeline_status, error_message } = report;

  if (pipeline_status === "error") {
    return (
      <div className="border border-red-200 bg-red-50 rounded-xl p-5">
        <p className="text-sm font-medium text-red-700">Pipeline error</p>
        <p className="text-sm text-red-600 mt-1">{error_message}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 w-full max-w-2xl mx-auto pb-16">

      {/* PMF Score — hero element */}
      {pmf_score && (
        <Section title="Product-Market Fit Score">
          <ScoreBadge score={pmf_score.score} verdict={pmf_score.verdict} />
          <p className="text-sm text-gray-600 leading-relaxed">{pmf_score.reasoning}</p>
          <div className="grid grid-cols-2 gap-3 pt-1">
            <div className="bg-green-50 rounded-lg p-3">
              <p className="text-xs font-medium text-green-700 mb-1">Strongest signal</p>
              <p className="text-xs text-gray-600">{pmf_score.strongest_signal}</p>
            </div>
            <div className="bg-orange-50 rounded-lg p-3">
              <p className="text-xs font-medium text-orange-700 mb-1">Biggest gap</p>
              <p className="text-xs text-gray-600">{pmf_score.biggest_gap}</p>
            </div>
          </div>
        </Section>
      )}

      {/* ICP Hypotheses */}
      {product_analysis && (
        <Section title="ICP Hypotheses">
          <p className="text-xs text-gray-500">{product_analysis.problem_being_solved}</p>
          <div className="space-y-2 pt-1">
            {product_analysis.icp_hypotheses.map((h, i) => (
              <div key={i} className="flex items-start gap-3 text-sm">
                <span className={`mt-0.5 flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold
                  ${h.pain_intensity >= 7 ? "bg-red-100 text-red-700" :
                    h.pain_intensity >= 5 ? "bg-yellow-100 text-yellow-700" :
                    "bg-gray-100 text-gray-500"}`}>
                  {h.pain_intensity}
                </span>
                <div className="min-w-0">
                  <p className="font-medium text-gray-800">{h.persona}</p>
                  <p className="text-gray-500 text-xs mt-0.5">{h.why_they_pay}</p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {h.communities.map((c) => (
                      <span key={c} className="text-xs bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full">{c}</span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
          {product_analysis.red_flags.length > 0 && (
            <div className="pt-2 border-t border-gray-100">
              <p className="text-xs font-medium text-red-600 mb-1">⚑ Red flags</p>
              <ul className="space-y-1">
                {product_analysis.red_flags.map((f, i) => (
                  <li key={i} className="text-xs text-gray-500">• {f}</li>
                ))}
              </ul>
            </div>
          )}
        </Section>
      )}

      {/* GTM Pack */}
      {gtm_pack ? (
        <Section title="GTM Pack">
          <p className="text-xs text-gray-500">
            Targeting: <span className="font-medium text-gray-700">{gtm_pack.target_persona}</span>
          </p>

          {/* Landing Page */}
          <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-4 space-y-1">
            <p className="text-xs font-medium text-indigo-500 uppercase tracking-wide">Landing Page</p>
            <p className="text-lg font-bold text-gray-900 leading-tight">{gtm_pack.landing_page_headline}</p>
            <p className="text-sm text-gray-600">{gtm_pack.landing_page_subheadline}</p>
          </div>

          <CopyBlock label="Cold DM" content={gtm_pack.cold_dm} />
          <CopyBlock label="Reddit Post Angle" content={gtm_pack.reddit_post_angle} />

          {gtm_pack.community_targets.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Community targets</p>
              <div className="flex flex-wrap gap-1">
                {gtm_pack.community_targets.map((c) => (
                  <span key={c} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{c}</span>
                ))}
              </div>
            </div>
          )}
        </Section>
      ) : (
        pipeline_status === "complete" && (
          <div className="border border-yellow-200 bg-yellow-50 rounded-xl p-4 text-sm text-yellow-800">
            <p className="font-medium">GTM copy skipped</p>
            <p className="text-xs mt-1 text-yellow-700">
              PMF signal was too weak — collect more community evidence before writing copy.
            </p>
          </div>
        )
      )}

    </div>
  );
}
