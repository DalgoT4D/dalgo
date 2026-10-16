import type { NotificationFilters, NotificationTab, NotificationType } from '@/types/notifications';
import { READ_STATUS } from '@/constants/notifications';

export function buildQueryString(filters: NotificationFilters): string {
  const params = new URLSearchParams();
  params.append('limit', String(filters.limit));
  params.append('page', String(filters.page));

  if (filters.read_status !== undefined) {
    params.append('read_status', String(filters.read_status));
  }
  // Repeated param: ?notification_type=pipeline&notification_type=sharing
  filters.notification_types?.forEach((t) => params.append('notification_type', t));
  if (filters.exclude_announcements) {
    params.append('exclude_announcements', 'true');
  }

  return `?${params.toString()}`;
}

export function buildFilters(
  tab: NotificationTab,
  page: number,
  pageSize: number,
  options?: {
    notification_types?: NotificationType[];
    exclude_announcements?: boolean;
  }
): NotificationFilters {
  const filters: NotificationFilters = {
    limit: pageSize,
    page: page,
    ...options,
  };

  if (tab === 'read') filters.read_status = READ_STATUS.READ;
  if (tab === 'unread') filters.read_status = READ_STATUS.UNREAD;

  return filters;
}
