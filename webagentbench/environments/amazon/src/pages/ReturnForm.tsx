import { useEffect, useState } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import { preserveQueryParams } from "@webagentbench/shared";

import type { Order } from "../types";
import { useAmazonLayout } from "../context";

const RETURN_REASONS = [
  { value: "defective", label: "Item is defective or doesn't work" },
  { value: "wrong_item", label: "Wrong item was sent" },
  { value: "no_longer_needed", label: "No longer needed" },
  { value: "arrived_too_late", label: "Item arrived too late" },
];

export function ReturnFormPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const { api, notify } = useAmazonLayout();
  const navigate = useNavigate();
  const location = useLocation();

  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedOrderId, setSelectedOrderId] = useState(orderId || "");
  const [selectedItemIndex, setSelectedItemIndex] = useState(0);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.getOrders()
      .then((items) => {
        if (cancelled) return;
        setOrders(items);
        if (orderId && items.find((o) => o.id === orderId)) {
          setSelectedOrderId(orderId);
        } else if (items.length > 0) {
          setSelectedOrderId(items[0].id);
        }
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [api, orderId]);

  const selectedOrder = orders.find((o) => o.id === selectedOrderId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOrderId || !reason) {
      notify("Error", "Please select an order, item, and reason.");
      return;
    }
    setSubmitting(true);
    try {
      await api.createReturn(selectedOrderId, selectedItemIndex, reason);
      notify("Return Requested", "Your return request has been submitted.");
      navigate(preserveQueryParams("/returns", location.search));
    } catch {
      notify("Error", "Failed to submit your return request.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="amazon-loading">
        <div className="amazon-spinner" />
        <p>Loading orders...</p>
      </div>
    );
  }

  if (orders.length === 0) {
    return (
      <div className="returns-empty">
        <h1>Request a Return</h1>
        <p>You have no orders to return.</p>
      </div>
    );
  }

  return (
    <div className="return-form-page">
      <h1>Request a Return</h1>

      <div className="return-form-page__card">
        <form onSubmit={handleSubmit}>
          <div className="return-form__field">
            <label htmlFor="return-order">Select Order</label>
            <select
              id="return-order"
              value={selectedOrderId}
              onChange={(e) => {
                setSelectedOrderId(e.target.value);
                setSelectedItemIndex(0);
              }}
              aria-label="Select order for return"
            >
              {orders.map((order) => (
                <option key={order.id} value={order.id}>
                  Order #{order.id} - {new Date(order.placed_at).toLocaleDateString()} - ${(order.total ?? 0).toFixed(2)} ({order.status})
                </option>
              ))}
            </select>
          </div>

          {selectedOrder && (selectedOrder.items ?? []).length > 0 && (
            <div className="return-form__field">
              <label htmlFor="return-item">Select Item</label>
              <select
                id="return-item"
                value={selectedItemIndex}
                onChange={(e) => setSelectedItemIndex(Number(e.target.value))}
                aria-label="Select item to return"
              >
                {selectedOrder.items.map((item, index) => (
                  <option key={index} value={index}>
                    {item.product_name} {item.variant_name ? `(${item.variant_name})` : ""} - Qty: {item.quantity} - ${(item.unit_price ?? 0).toFixed(2)}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="return-form__field">
            <label htmlFor="return-reason">Reason for Return</label>
            <select
              id="return-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              aria-label="Reason for return"
            >
              <option value="">-- Select a reason --</option>
              {RETURN_REASONS.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>

          {selectedOrder && selectedItemIndex < selectedOrder.items.length && (
            <div className="return-form__preview">
              <h3>Return Preview</h3>
              <div className="return-form__preview-item">
                <div className="cart-item__image-placeholder"><span>P</span></div>
                <div>
                  <strong>{selectedOrder.items[selectedItemIndex].product_name}</strong>
                  <div>Price: ${(selectedOrder.items[selectedItemIndex].unit_price ?? 0).toFixed(2)}</div>
                  <div>Quantity: {selectedOrder.items[selectedItemIndex].quantity}</div>
                </div>
              </div>
            </div>
          )}

          <div className="return-form__actions">
            <button
              type="button"
              className="amazon-btn amazon-btn--wishlist"
              onClick={() => navigate(preserveQueryParams("/returns", location.search))}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="amazon-btn amazon-btn--add-to-cart"
              disabled={submitting || !reason}
            >
              {submitting ? "Submitting..." : "Submit Return Request"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
