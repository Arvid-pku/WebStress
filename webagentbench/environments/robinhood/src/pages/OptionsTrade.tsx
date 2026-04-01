import { useEffect, useState } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import { Button, preserveQueryParams } from "@webagentbench/shared";

import { useRobinhoodLayout } from "../context";
import type { OptionsContract } from "../types";

const STRATEGIES = [
  { value: "single", label: "Single" },
  { value: "vertical", label: "Vertical Spread" },
  { value: "iron_condor", label: "Iron Condor" },
  { value: "straddle", label: "Straddle" },
  { value: "strangle", label: "Strangle" },
  { value: "covered_call", label: "Covered Call" },
  { value: "protective_put", label: "Protective Put" },
];

export function OptionsTradePage() {
  const { symbol } = useParams<{ symbol: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const { api, notify } = useRobinhoodLayout();
  const [contracts, setContracts] = useState<OptionsContract[]>([]);
  const [loading, setLoading] = useState(true);
  const [strategy, setStrategy] = useState("single");
  const [selectedContract, setSelectedContract] = useState<OptionsContract | null>(null);
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [quantity, setQuantity] = useState("1");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!symbol) return;
    let cancelled = false;
    api.getOptionsChain(symbol)
      .then((c) => {
        if (!cancelled) {
          setContracts(c);
          if (c.length > 0) setSelectedContract(c[0]);
        }
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [api, symbol]);

  if (loading) return <div className="rh-loading">Loading...</div>;

  const premium = selectedContract
    ? parseFloat(selectedContract.ask) * parseInt(quantity || "0") * 100
    : 0;

  const handleSubmit = async () => {
    if (!selectedContract) return;
    setIsSubmitting(true);
    try {
      await api.placeOptionsOrder({
        strategy,
        legs: [{
          side,
          option_type: selectedContract.option_type,
          strike: selectedContract.strike,
          expiration: selectedContract.expiration,
          quantity: parseInt(quantity) || 1,
          premium: selectedContract.ask,
        }],
      });
      notify("Options Order Placed", `${side} ${quantity} ${selectedContract.option_type} ${symbol} $${selectedContract.strike}`);
      navigate(preserveQueryParams(`/stocks/${symbol}/options`, location.search));
    } catch (err) {
      notify("Order Failed", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="rh-options-trade" aria-label={`Trade ${symbol} options`}>
      <div className="rh-options-trade__header">
        <button
          className="rh-back-btn"
          onClick={() => navigate(preserveQueryParams(`/stocks/${symbol}/options`, location.search))}
          aria-label="Back to options chain"
        >
          ← {symbol} Options
        </button>
        <h1>Trade {symbol} Options</h1>
      </div>

      <div className="rh-order-form__field">
        <label htmlFor="opt-strategy">Strategy</label>
        <select id="opt-strategy" value={strategy} onChange={(e) => setStrategy(e.target.value)}>
          {STRATEGIES.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
      </div>

      <div className="rh-order-form__tabs">
        <button className={`rh-order-form__tab ${side === "buy" ? "rh-order-form__tab--active" : ""}`} onClick={() => setSide("buy")}>Buy</button>
        <button className={`rh-order-form__tab ${side === "sell" ? "rh-order-form__tab--active" : ""}`} onClick={() => setSide("sell")}>Sell</button>
      </div>

      <div className="rh-order-form__field">
        <label htmlFor="opt-contract">Contract</label>
        <select
          id="opt-contract"
          value={selectedContract?.contract_id ?? ""}
          onChange={(e) => setSelectedContract(contracts.find((c) => c.contract_id === e.target.value) ?? null)}
        >
          {contracts.map((c) => (
            <option key={c.contract_id} value={c.contract_id}>
              {c.option_type.toUpperCase()} ${parseFloat(c.strike).toFixed(2)} exp {c.expiration}
            </option>
          ))}
        </select>
      </div>

      <div className="rh-order-form__field">
        <label htmlFor="opt-qty">Contracts</label>
        <input id="opt-qty" type="number" min="1" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
      </div>

      {selectedContract && (
        <div className="rh-order-form__summary">
          <div className="rh-order-form__row"><span>Bid</span><span>${parseFloat(selectedContract.bid).toFixed(2)}</span></div>
          <div className="rh-order-form__row"><span>Ask</span><span>${parseFloat(selectedContract.ask).toFixed(2)}</span></div>
          <div className="rh-order-form__row"><span>Estimated Premium</span><span>${premium.toFixed(2)}</span></div>
        </div>
      )}

      <Button
        variant="primary"
        disabled={!selectedContract || isSubmitting}
        onClick={handleSubmit}
        aria-label="Submit options order"
      >
        {isSubmitting ? "Submitting..." : `Submit ${side === "buy" ? "Buy" : "Sell"} Order`}
      </Button>
    </div>
  );
}
