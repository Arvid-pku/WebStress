import type { Notification } from "../types";

interface NotificationItemProps {
  notification: Notification;
  onMarkRead?: (id: string) => void;
}

const TYPE_ICONS: Record<string, string> = {
  order_fill: "receipt",
  price_alert: "chart",
  dividend: "cash",
  earnings: "calendar",
  transfer_complete: "bank",
  security_alert: "shield",
  recurring_investment: "refresh",
  tax_document: "document",
  margin_call: "warning",
  corporate_action: "briefcase",
};

export function NotificationItem({ notification, onMarkRead }: NotificationItemProps) {
  const ts = new Date(notification.timestamp);
  const timeStr = ts.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
  const iconType = TYPE_ICONS[notification.type] ?? "bell";

  return (
    <div
      className={`rh-notification-item ${notification.is_read ? "" : "rh-notification-item--unread"}`}
      onClick={() => !notification.is_read && onMarkRead?.(notification.id)}
      role="button"
      tabIndex={0}
      aria-label={`${notification.is_read ? "" : "Unread: "}${notification.title}`}
    >
      <div className="rh-notification-item__icon" data-type={iconType}>
        <span>{iconType.charAt(0).toUpperCase()}</span>
      </div>
      <div className="rh-notification-item__content">
        <div className="rh-notification-item__title">{notification.title}</div>
        <div className="rh-notification-item__message">{notification.message}</div>
        <div className="rh-notification-item__time">{timeStr}</div>
      </div>
      {!notification.is_read && <div className="rh-notification-item__dot" />}
    </div>
  );
}
