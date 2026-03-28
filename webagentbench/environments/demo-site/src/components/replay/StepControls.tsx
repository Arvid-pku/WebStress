"use client";

import { useEffect, useRef, useState } from "react";

interface StepControlsProps {
  current: number;
  total: number;
  onStep: (index: number) => void;
  isBusy?: boolean;
}

export function StepControls({ current, total, onStep, isBusy = false }: StepControlsProps) {
  const [playing, setPlaying] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (playing && !isBusy && current < total - 1) {
      timerRef.current = setTimeout(() => {
        onStep(current + 1);
      }, 1650);
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [playing, isBusy, current, total, onStep]);

  useEffect(() => {
    if (current >= total - 1) setPlaying(false);
  }, [current, total]);

  const btnClass =
    "text-sm px-3 py-1 border border-[var(--border)] rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--text-tertiary)] transition-colors disabled:opacity-30 disabled:pointer-events-none bg-transparent";

  return (
    <div className="flex items-center gap-3">
      <button onClick={() => onStep(Math.max(0, current - 1))} disabled={current === 0} className={btnClass}>
        &larr;
      </button>
      <button onClick={() => setPlaying((p) => !p)} className={btnClass}>
        {playing ? "Pause" : "Play"}
      </button>
      <button onClick={() => onStep(Math.min(total - 1, current + 1))} disabled={current >= total - 1} className={btnClass}>
        &rarr;
      </button>
      <span className="text-[12px] text-[var(--text-tertiary)]">
        Step {current + 1} of {total}
      </span>
      {isBusy ? (
        <span className="text-[12px] text-[var(--accent)]">Syncing…</span>
      ) : null}
    </div>
  );
}
