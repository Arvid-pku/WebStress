"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { TrajectoryViewer } from "@/components/replay/TrajectoryViewer";

interface TrajectoryStep {
  step: number;
  thought: string;
  action: Record<string, unknown>;
  targets: { role: string; name: string };
  status: string;
  elapsed_seconds: number;
}

interface TrajectoryData {
  task_id: string;
  title: string;
  instruction: string;
  difficulty: string;
  model: string;
  total_steps: number;
  elapsed_seconds: number;
  completed: boolean;
  evaluation: {
    score: number;
    success: boolean;
    reasoning: string;
    criteria_results?: Array<{ desc: string; passed: boolean; penalty?: number }>;
  };
  steps: TrajectoryStep[];
}

export default function TrajectoryPage({ taskId }: { taskId: string }) {
  const [data, setData] = useState<TrajectoryData | null>(null);
  const [showInstruction, setShowInstruction] = useState(false);

  useEffect(() => {
    fetch(`/results/trajectories/${taskId}.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setData)
      .catch(() => setData(null));
  }, [taskId]);

  if (!data) {
    return (
      <div className="max-w-[720px] mx-auto px-12 py-20">
        <Link href="/results" className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] no-underline">
          ← Results
        </Link>
        <p className="mt-8 text-[var(--text-secondary)]">Loading trajectory...</p>
      </div>
    );
  }

  const score = data.evaluation?.score;
  const success = data.evaluation?.success;

  return (
    <div className="max-w-[960px] mx-auto px-12 py-20">
      <Link href="/results" className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] no-underline">
        ← Results
      </Link>

      {/* Header */}
      <div className="mt-6 mb-8">
        <h1 className="text-2xl font-medium tracking-tight">{data.title}</h1>
        <div className="flex gap-4 mt-2 font-mono text-sm">
          <span className="text-[var(--text-tertiary)]">{data.difficulty}</span>
          <span className={success ? "text-[var(--green)]" : "text-[var(--red)]"}>
            {score !== undefined ? score.toFixed(2) : "—"}
          </span>
          <span className="text-[var(--text-tertiary)]">
            {data.total_steps} steps · {data.elapsed_seconds.toFixed(0)}s
          </span>
        </div>
      </div>

      {/* Collapsible instruction */}
      <button
        onClick={() => setShowInstruction(!showInstruction)}
        className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] mb-6 cursor-pointer bg-transparent border-none font-[inherit]"
      >
        {showInstruction ? "▾ Hide instruction" : "▸ Show instruction"}
      </button>
      {showInstruction && (
        <div className="mb-8 p-4 bg-[var(--surface)] border border-[var(--border)] rounded text-sm text-[var(--text-secondary)] leading-relaxed">
          {data.instruction}
        </div>
      )}

      {/* Trajectory viewer (manages its own step state + controls) */}
      <TrajectoryViewer steps={data.steps} />

      {/* Evaluation panel */}
      {data.evaluation && (
        <div className="mt-12 border-t border-[var(--border)] pt-8">
          <p className="font-mono text-xs tracking-[3px] uppercase text-[var(--text-tertiary)] mb-4">
            Evaluation
          </p>
          {data.evaluation.reasoning && (
            <p className="text-sm text-[var(--text-secondary)] mb-4 leading-relaxed">
              {data.evaluation.reasoning}
            </p>
          )}
          {data.evaluation.criteria_results && data.evaluation.criteria_results.length > 0 && (
            <div className="flex flex-col gap-2">
              {data.evaluation.criteria_results.map((cr, i) => (
                <div key={i} className="flex items-baseline gap-2 text-sm">
                  <span className={cr.passed ? "text-[var(--green)]" : "text-[var(--red)]"}>
                    {cr.passed ? "✓" : "✗"}
                  </span>
                  <span className="text-[var(--text-secondary)]">{cr.desc}</span>
                  {cr.penalty !== undefined && !cr.passed && (
                    <span className="font-mono text-xs text-[var(--text-tertiary)]">
                      (-{cr.penalty})
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
