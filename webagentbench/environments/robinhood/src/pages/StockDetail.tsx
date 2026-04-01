import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { Button, preserveQueryParams } from "@webagentbench/shared";

import { useRobinhoodLayout } from "../context";
import type { Position, Stock } from "../types";
import { StockChart } from "../components/StockChart";
import { StatsGrid } from "../components/StatsGrid";

export function StockDetailPage() {
  const { symbol } = useParams<{ symbol: string }>();
  const location = useLocation();
  const { api } = useRobinhoodLayout();
  const [stock, setStock] = useState<Stock | null>(null);
  const [position, setPosition] = useState<Position | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!symbol) return;
    let cancelled = false;
    (async () => {
      try {
        const s = await api.getStock(symbol);
        if (!cancelled) setStock(s);
      } catch { /* skip */ }
      try {
        const p = await api.getPosition(symbol);
        if (!cancelled) setPosition(p);
      } catch { /* no position */ }
      if (!cancelled) setLoading(false);
    })();
    return () => { cancelled = true; };
  }, [api, symbol]);

  if (loading) return <div className="rh-loading">Loading...</div>;
  if (!stock) return <div className="rh-empty">Stock not found: {symbol}</div>;

  const price = parseFloat(stock.price);
  const dayChange = parseFloat(stock.day_change);
  const dayChangePct = parseFloat(stock.day_change_pct);
  const isPositive = dayChange >= 0;

  const formatNum = (v: string | null) =>
    v ? parseFloat(v).toLocaleString("en-US", { maximumFractionDigits: 2 }) : null;

  const stats = [
    { label: "Market Cap", value: stock.market_cap ? `$${formatNum(stock.market_cap)}` : null },
    { label: "P/E Ratio", value: formatNum(stock.pe_ratio) },
    { label: "EPS", value: stock.eps ? `$${formatNum(stock.eps)}` : null },
    { label: "Div Yield", value: stock.dividend_yield ? `${formatNum(stock.dividend_yield)}%` : null },
    { label: "52W High", value: `$${formatNum(stock.fifty_two_week_high)}` },
    { label: "52W Low", value: `$${formatNum(stock.fifty_two_week_low)}` },
    { label: "Volume", value: stock.volume.toLocaleString() },
    { label: "Avg Volume", value: stock.avg_volume.toLocaleString() },
    { label: "Bid", value: `$${formatNum(stock.bid)} x ${stock.bid_size}` },
    { label: "Ask", value: `$${formatNum(stock.ask)} x ${stock.ask_size}` },
  ];

  return (
    <div className="rh-stock-detail" aria-label={`${stock.name} stock details`}>
      <div className="rh-stock-detail__header">
        <h1 className="rh-stock-detail__name">{stock.name}</h1>
        <div className="rh-stock-detail__price">
          <span className="rh-stock-detail__price-value">${price.toFixed(2)}</span>
          <span className={`rh-stock-detail__day-change ${isPositive ? "rh-gain" : "rh-loss"}`}>
            {isPositive ? "+" : ""}${dayChange.toFixed(2)} ({isPositive ? "+" : ""}{dayChangePct.toFixed(2)}%)
          </span>
        </div>
      </div>

      <StockChart data={stock.historical_prices} positive={isPositive} />

      <div className="rh-stock-detail__actions">
        <Link to={preserveQueryParams(`/stocks/${symbol}/trade`, location.search)}>
          <Button variant="primary" className="rh-btn--buy" aria-label={`Trade ${symbol}`}>
            Trade {symbol}
          </Button>
        </Link>
        <Link to={preserveQueryParams(`/stocks/${symbol}/options`, location.search)}>
          <Button variant="secondary" aria-label={`View ${symbol} options`}>
            Options
          </Button>
        </Link>
      </div>

      {position && (
        <section className="rh-stock-detail__position" aria-label="Your position">
          <h2>Your Position</h2>
          <div className="rh-stats-grid">
            <div className="rh-stats-grid__item">
              <span className="rh-stats-grid__label">Shares</span>
              <span className="rh-stats-grid__value">{parseFloat(position.quantity)}</span>
            </div>
            <div className="rh-stats-grid__item">
              <span className="rh-stats-grid__label">Avg Cost</span>
              <span className="rh-stats-grid__value">${parseFloat(position.avg_cost_basis).toFixed(2)}</span>
            </div>
            <div className="rh-stats-grid__item">
              <span className="rh-stats-grid__label">Total Return</span>
              <span className={`rh-stats-grid__value ${parseFloat(position.total_return) >= 0 ? "rh-gain" : "rh-loss"}`}>
                ${parseFloat(position.total_return).toFixed(2)} ({parseFloat(position.total_return_pct).toFixed(2)}%)
              </span>
            </div>
            <div className="rh-stats-grid__item">
              <span className="rh-stats-grid__label">Equity</span>
              <span className="rh-stats-grid__value">
                ${(parseFloat(position.quantity) * parseFloat(position.current_price)).toFixed(2)}
              </span>
            </div>
          </div>
        </section>
      )}

      <section className="rh-stock-detail__stats" aria-label="Key statistics">
        <h2>Key Statistics</h2>
        <StatsGrid stats={stats} />
      </section>

      <section className="rh-stock-detail__about" aria-label="About">
        <h2>About</h2>
        <p>{stock.about}</p>
        <div className="rh-stock-detail__meta">
          <span>Sector: {stock.sector}</span>
          <span>Industry: {stock.industry}</span>
        </div>
      </section>
    </div>
  );
}
