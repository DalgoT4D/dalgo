'use client';

import { Badge } from '@/components/ui/badge';
import { NOTIFICATION_TYPE_LABELS } from '@/constants/notifications';
import type { NotificationType } from '@/types/notifications';

interface NotificationTypeBadgeProps {
  type: NotificationType | null;
  className?: string;
}

export function NotificationTypeBadge({ type, className }: NotificationTypeBadgeProps) {
  if (!type) return null;

  return (
    <Badge
      variant="outline"
      data-testid={`notification-type-badge-${type}`}
      className={`rounded-full bg-primary/10 text-primary border-primary/20 hover:bg-primary/10 ${className ?? ''}`}
    >
      {NOTIFICATION_TYPE_LABELS[type]}
    </Badge>
  );
}
