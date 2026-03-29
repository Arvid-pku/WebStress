export default function ArchitecturePage() {
  return (
    <>
      <p className="text-[12px] font-medium text-[var(--text-tertiary)] mb-8">
        Documentation / Architecture
      </p>
      <h1 className="text-2xl font-medium tracking-tight mb-3">Architecture</h1>
      <p className="text-[14px] text-[var(--text-secondary)] leading-[1.7] mb-12">
        LLMOS is built around a clean separation between deterministic Python logic and LLM
        predictions. This page covers the core architectural decisions that make the simulator and
        benchmark interoperable.
      </p>

      {/* 1. Sandwich Architecture */}
      <section className="mb-14">
        <h2 id="sandwich-architecture" className="text-lg font-medium tracking-tight mb-3">
          Sandwich Architecture
        </h2>
        <p className="text-[14px] text-[var(--text-secondary)] leading-[1.7] mb-6">
          Python handles all deterministic operations — input validation, state mutation, patching —
          while LLMs are responsible only for predictions. This &ldquo;sandwich&rdquo; pattern keeps
          the system auditable and prevents LLMs from corrupting internal state directly.
        </p>
        <div className="border border-[var(--border)] rounded-xl overflow-hidden">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
                <th className="text-left px-4 py-3 font-medium text-[var(--text-secondary)]">
                  Layer
                </th>
                <th className="text-left px-4 py-3 font-medium text-[var(--text-secondary)]">
                  Responsibility
                </th>
                <th className="text-left px-4 py-3 font-medium text-[var(--text-secondary)]">
                  Handler
                </th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-[var(--border)]">
                <td className="px-4 py-3 font-medium text-[var(--text-primary)]">Input validation</td>
                <td className="px-4 py-3 text-[var(--text-secondary)]">
                  Parse and validate agent actions before they reach the simulator
                </td>
                <td className="px-4 py-3">
                  <span className="text-[var(--accent)] font-mono">Python</span>
                </td>
              </tr>
              <tr className="border-b border-[var(--border)]">
                <td className="px-4 py-3 font-medium text-[var(--text-primary)]">Prediction</td>
                <td className="px-4 py-3 text-[var(--text-secondary)]">
                  Predict how the UI state changes in response to an action
                </td>
                <td className="px-4 py-3">
                  <span className="text-[var(--accent)] font-mono">LLM</span>
                </td>
              </tr>
              <tr>
                <td className="px-4 py-3 font-medium text-[var(--text-primary)]">State mutation</td>
                <td className="px-4 py-3 text-[var(--text-secondary)]">
                  Apply the predicted patch to the canonical state object
                </td>
                <td className="px-4 py-3">
                  <span className="text-[var(--accent)] font-mono">Python</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* 2. Unified Agent Format */}
      <section className="mb-14">
        <h2 id="unified-format" className="text-lg font-medium tracking-tight mb-3">
          Unified Agent Format
        </h2>
        <p className="text-[14px] text-[var(--text-secondary)] leading-[1.7] mb-5">
          Both the LLMOS simulator and WebAgentBench use the same indexed accessibility tree format
          for observations. This means an agent trained in simulation sees identical input structure
          when evaluated on a real browser.
        </p>
        <p className="text-[14px] text-[var(--text-secondary)] leading-[1.7] mb-3">
          Observations are rendered as indented trees with numeric reference indices:
        </p>
        <div className="border border-[var(--border)] rounded-xl bg-[var(--surface-raised)] p-5 font-mono text-[13px] mb-5 leading-[1.8]">
          <span className="text-[var(--text-tertiary)]">[1]</span>{" "}
          <span className="text-[var(--accent)]">button</span>{" "}
          <span className="text-[var(--text-primary)]">&quot;Settings&quot;</span>
          <br />
          <span className="text-[var(--text-tertiary)]">[2]</span>{" "}
          <span className="text-[var(--accent)]">textbox</span>{" "}
          <span className="text-[var(--text-primary)]">&quot;Search&quot;</span>
          <br />
          {"  "}
          <span className="text-[var(--text-tertiary)]">[3]</span>{" "}
          <span className="text-[var(--accent)]">option</span>{" "}
          <span className="text-[var(--text-primary)]">&quot;Option A&quot;</span>
        </div>
        <p className="text-[14px] text-[var(--text-secondary)] leading-[1.7] mb-3">
          Actions are JSON objects that reference elements by their index:
        </p>
        <div className="border border-[var(--border)] rounded-xl bg-[var(--surface-raised)] p-5 font-mono text-[13px] leading-[1.8]">
          <div className="mb-1">
            <span className="text-[var(--text-tertiary)]">{"// click"}</span>
          </div>
          <div className="mb-3">
            {"{"}
            <span className="text-[var(--accent)]">&quot;action&quot;</span>
            {": "}
            <span className="text-[var(--text-primary)]">&quot;click&quot;</span>
            {", "}
            <span className="text-[var(--accent)]">&quot;ref&quot;</span>
            {": "}
            <span className="text-[var(--text-primary)]">1</span>
            {"}"}
          </div>
          <div className="mb-1">
            <span className="text-[var(--text-tertiary)]">{"// fill"}</span>
          </div>
          <div>
            {"{"}
            <span className="text-[var(--accent)]">&quot;action&quot;</span>
            {": "}
            <span className="text-[var(--text-primary)]">&quot;fill&quot;</span>
            {", "}
            <span className="text-[var(--accent)]">&quot;ref&quot;</span>
            {": "}
            <span className="text-[var(--text-primary)]">2</span>
            {", "}
            <span className="text-[var(--accent)]">&quot;value&quot;</span>
            {": "}
            <span className="text-[var(--text-primary)]">&quot;hello&quot;</span>
            {"}"}
          </div>
        </div>
      </section>

      {/* 3. Adapters */}
      <section className="mb-14">
        <h2 id="adapters" className="text-lg font-medium tracking-tight mb-3">
          Adapters
        </h2>
        <p className="text-[14px] text-[var(--text-secondary)] leading-[1.7] mb-6">
          Two adapter modules in <span className="font-mono text-[var(--text-primary)]">shared/</span>{" "}
          bridge the unified format to their respective backends:
        </p>
        <div className="flex flex-col gap-3">
          <div className="border border-[var(--border)] rounded-xl p-5">
            <p className="font-mono text-[13px] text-[var(--accent)] mb-2">llmos_adapter.py</p>
            <p className="text-[13px] text-[var(--text-secondary)] leading-[1.6]">
              Converts between LLMOS internal state (bid-based element identifiers) and the unified
              indexed accessibility tree format. Used during simulator episodes so the agent always
              sees the standard observation structure.
            </p>
          </div>
          <div className="border border-[var(--border)] rounded-xl p-5">
            <p className="font-mono text-[13px] text-[var(--accent)] mb-2">playwright_adapter.py</p>
            <p className="text-[13px] text-[var(--text-secondary)] leading-[1.6]">
              Converts between Playwright&apos;s{" "}
              <span className="font-mono text-[var(--text-primary)]">aria_snapshot</span> format and
              the unified indexed tree, and also executes unified actions on real browser pages.
              Used by WebAgentBench during live evaluation.
            </p>
          </div>
        </div>
      </section>

      {/* 4. State Visibility Rules */}
      <section className="mb-14">
        <h2 id="state-visibility" className="text-lg font-medium tracking-tight mb-3">
          State Visibility Rules
        </h2>
        <p className="text-[14px] text-[var(--text-secondary)] leading-[1.7] mb-6">
          Different actors in the system see different slices of the world state. Hidden state
          exists to simulate real-world unknowns the agent must discover through interaction.
        </p>
        <div className="border border-[var(--border)] rounded-xl overflow-hidden">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--surface)]">
                <th className="text-left px-4 py-3 font-medium text-[var(--text-secondary)]">
                  Actor
                </th>
                <th className="text-left px-4 py-3 font-medium text-[var(--text-secondary)]">
                  Visible state
                </th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-[var(--border)]">
                <td className="px-4 py-3 font-medium text-[var(--text-primary)]">Simulator</td>
                <td className="px-4 py-3 text-[var(--text-secondary)]">
                  Full state including{" "}
                  <span className="font-mono text-[var(--text-primary)]">hidden_state</span>
                </td>
              </tr>
              <tr className="border-b border-[var(--border)]">
                <td className="px-4 py-3 font-medium text-[var(--text-primary)]">Agent</td>
                <td className="px-4 py-3 text-[var(--text-secondary)]">
                  Filtered observation only — no hidden information
                </td>
              </tr>
              <tr>
                <td className="px-4 py-3 font-medium text-[var(--text-primary)]">Judge</td>
                <td className="px-4 py-3 text-[var(--text-secondary)]">
                  Full state plus complete episode history
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* 5. Episode Loop */}
      <section className="mb-14">
        <h2 id="episode-loop" className="text-lg font-medium tracking-tight mb-3">
          Episode Loop
        </h2>
        <p className="text-[14px] text-[var(--text-secondary)] leading-[1.7] mb-6">
          Each episode follows a fixed four-phase loop. The agent never interacts with the
          simulator directly — all state transitions go through the validated Python layer.
        </p>
        <div className="flex items-center gap-2 flex-wrap">
          {[
            { label: "Reset", desc: "Initialize state" },
            { label: "Agent.act", desc: "obs → action" },
            { label: "Simulator.step", desc: "action → patch" },
            { label: "Judge.evaluate", desc: "score episode" },
          ].map((step, i, arr) => (
            <div key={step.label} className="flex items-center gap-2">
              <div className="border border-[var(--border)] rounded-xl bg-[var(--surface-raised)] px-4 py-3 text-center min-w-[120px]">
                <p className="text-[13px] font-medium text-[var(--text-primary)]">{step.label}</p>
                <p className="text-[11px] text-[var(--text-tertiary)] mt-0.5">{step.desc}</p>
              </div>
              {i < arr.length - 1 && (
                <span className="text-[var(--text-tertiary)] text-[18px] leading-none select-none">
                  →
                </span>
              )}
            </div>
          ))}
        </div>
        <p className="text-[13px] text-[var(--text-tertiary)] mt-4 leading-[1.6]">
          The loop repeats Agent.act → Simulator.step until the episode terminates, then
          Judge.evaluate scores the final state.
        </p>
      </section>

      {/* 6. Multi-Provider LLM Support */}
      <section className="mb-14">
        <h2 id="multi-provider" className="text-lg font-medium tracking-tight mb-3">
          Multi-Provider LLM Support
        </h2>
        <p className="text-[14px] text-[var(--text-secondary)] leading-[1.7] mb-6">
          Both the agent and simulator support three LLM providers, selectable independently via
          CLI flags. The vLLM provider uses an OpenAI-compatible endpoint, which is also how
          Tinker inference works.
        </p>
        <div className="flex flex-col gap-3">
          {[
            {
              name: "openai",
              flag: "--agent-provider openai",
              desc: "GPT-4o, GPT-4o-mini, and other OpenAI models via the standard API.",
            },
            {
              name: "gemini",
              flag: "--agent-provider gemini",
              desc: "Gemini 2.5 Pro, Gemini Flash, and other Google models via the Gemini API.",
            },
            {
              name: "vllm",
              flag: "--agent-provider vllm",
              desc: "Self-hosted or Tinker-hosted models via an OpenAI-compatible endpoint. Used for finetuned Qwen inference.",
            },
          ].map((p) => (
            <div key={p.name} className="border border-[var(--border)] rounded-xl p-5">
              <div className="flex items-center gap-3 mb-2">
                <span className="font-mono text-[13px] text-[var(--accent)]">{p.name}</span>
                <span className="font-mono text-[11px] text-[var(--text-tertiary)] bg-[var(--surface)] px-2 py-0.5 rounded-md">
                  {p.flag}
                </span>
              </div>
              <p className="text-[13px] text-[var(--text-secondary)] leading-[1.6]">{p.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
