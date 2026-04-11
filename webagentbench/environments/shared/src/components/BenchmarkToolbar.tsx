import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";

import { useAdapterContext } from "../hooks/useAdapter";
import { preserveQueryParams } from "../utils/navigation";

interface EvaluationCheck {
  desc?: string;
  expr?: string;
  passed: boolean;
  penalty?: number;
}

interface EvaluationResult {
  score?: number;
  final_score?: number;
  success?: boolean;
  checks?: EvaluationCheck[];
  negative_checks?: EvaluationCheck[];
  reasoning?: string;
  detail?: string;
}

interface SessionInfoResponse {
  session_id?: string;
  start_path?: string;
  instruction?: string;
  title?: string;
  degradation?: {
    variant_filename?: string;
    injections?: Array<Record<string, unknown>>;
  };
      );
    } catch (error) {
      setRecordMessage(`Reset failed: ${(error as Error).message}`);
    }
  };

  const score = evaluation?.score ?? evaluation?.final_score ?? 0;
  const checks = evaluation?.checks ?? [];
  const negativeChecks = evaluation?.negative_checks ?? [];
  const launchHref = preserveQueryParams("/launch", location.search, ["agent_mode"]);

  return (
    <div className="wab-bench-toolbar">
      <button
        type="button"
        className="wab-bench-toolbar__tab"
        aria-label="Toggle WebAgentBench toolbar"
        onClick={() => setOpen((current) => !current)}
      >
        WAB
      </button>
      <section className={`wab-bench-toolbar__panel${open ? " wab-bench-toolbar__panel--open" : ""}`}>
        <header className="wab-bench-toolbar__header">
          <span className="wab-bench-toolbar__label">WebAgentBench</span>
          <button
            type="button"
            className="wab-bench-toolbar__close"
            aria-label="Close toolbar"
            onClick={() => setOpen(false)}
          >
            ×
          </button>
        </header>
        <div className="wab-bench-toolbar__instruction" title={instruction}>{instruction}</div>
        <div className="wab-bench-toolbar__actions">
          <button
            type="button"
            className={`wab-bench-toolbar__button wab-bench-toolbar__button--secondary${recording ? " wab-bench-toolbar__button--recording" : ""}`}
            onClick={() => { void handleToggleRecord(); }}
          >
            {recording ? `⏹ Stop (${recordCount})` : "⏺ Record"}
          </button>
          <button
            type="button"
            className="wab-bench-toolbar__button wab-bench-toolbar__button--primary"
            disabled={evaluateBusy}
            onClick={() => { void handleEvaluate(); }}
          >
            {evaluateBusy ? "Evaluating..." : "Evaluate"}
          </button>
          <button
            type="button"
            className="wab-bench-toolbar__button wab-bench-toolbar__button--secondary"
            onClick={() => { void handleReset(); }}
          >
            Reset
          </button>
          <a className="wab-bench-toolbar__button wab-bench-toolbar__button--secondary wab-bench-toolbar__launcher" href={launchHref}>
            ← Launcher
          </a>
        </div>
        {recordMessage ? <div className="wab-bench-toolbar__message">{recordMessage}</div> : null}
        {evaluation ? (
          <div className="wab-bench-toolbar__results">
            <div className="wab-bench-toolbar__score-row">
              <span className={`wab-bench-toolbar__score${evaluation.success ? " wab-bench-toolbar__score--pass" : " wab-bench-toolbar__score--fail"}`}>
                {score.toFixed(2)}
              </span>
              <span>{evaluation.success ? "PASSED" : "FAILED"}</span>
            </div>
            {checks.length > 0 ? <div className="wab-bench-toolbar__section-title">Checks</div> : null}
            {checks.map((check, index) => (
              <div key={`check-${index}`} className={`wab-bench-toolbar__check${check.passed ? " wab-bench-toolbar__check--pass" : " wab-bench-toolbar__check--fail"}`}>
                {check.passed ? "✓" : "✗"} {check.desc || check.expr}
              </div>
            ))}
            {negativeChecks.length > 0 ? <div className="wab-bench-toolbar__section-title">Negative Checks</div> : null}
            {negativeChecks.map((check, index) => (
              <div key={`negative-${index}`} className={`wab-bench-toolbar__check${check.passed ? " wab-bench-toolbar__check--pass" : " wab-bench-toolbar__check--fail"}`}>
                {check.passed ? "✓" : `✗ (-${(check.penalty ?? 0).toFixed(2)})`} {check.desc || check.expr}
              </div>
            ))}
            {evaluation.reasoning ? (
              <pre className="wab-bench-toolbar__reasoning">{evaluation.reasoning}</pre>
            ) : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}
