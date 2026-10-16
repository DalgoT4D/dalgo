import { formatDistanceToNow } from 'date-fns';
import { AlertCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { Checkbox } from '@/components/ui/checkbox';
import { TableCell, TableRow } from '@/components/ui/table';
import type { Notification } from '@/types/notifications';
import { cn } from '@/lib/utils';
import { renderMessageWithLinks } from '@/lib/notificationMessage';
import { NotificationTypeBadge } from '@/components/notifications/NotificationTypeBadge';

interface NotificationRowProps {
  notification: Notification;
  isSelected: boolean;
  isExpanded: boolean;
  onSelect: (id: number, checked: boolean) => void;
  onToggleExpand: (id: number) => void;
}

export function NotificationRow({
  notification,
  isSelected,
  isExpanded,
  onSelect,
  onToggleExpand,
}: NotificationRowProps) {
  // line-clamp-2 at text-sm clips at ~120 chars per line; also treat any newline as needing expand
  const isTruncatable = notification.message.length > 120 || notification.message.includes('\n');
  const isRead = notification.read_status;

  return (
    <TableRow
      data-testid={`notification-row-${notification.id}`}
      className={cn(
        'cursor-pointer',
        isRead ? 'bg-gray-50 hover:bg-gray-100' : 'bg-white hover:bg-gray-50/50'
      )}
      onClick={() => onToggleExpand(notification.id)}
    >
      {/* Stop propagation so checkbox click only selects, doesn't expand */}
      <TableCell className="w-12 pl-4 align-top py-4" onClick={(e) => e.stopPropagation()}>
        <Checkbox
          data-testid={`notification-checkbox-${notification.id}`}
          checked={isSelected}
          onCheckedChange={(checked) => onSelect(notification.id, checked as boolean)}
          aria-label={`Select notification ${notification.id}`}
          className={cn(
            isRead
              ? 'border-gray-300 data-[state=checked]:bg-gray-400 data-[state=checked]:border-gray-400'
              : 'border-gray-800 data-[state=checked]:bg-gray-900 data-[state=checked]:border-gray-900'
          )}
        />
      </TableCell>

      <TableCell className="w-full py-4 pr-6 align-top whitespace-normal">
        <p
          className={cn(
            'leading-relaxed text-sm break-words whitespace-pre-wrap min-h-[2.5rem]',
            !isExpanded && 'line-clamp-2',
            isRead ? 'text-gray-500 font-normal' : 'text-gray-800 font-medium'
          )}
        >
          {renderMessageWithLinks(notification.message)}
        </p>
        <div className="flex items-center gap-2 mt-2">
          <span className={cn('text-sm', isRead ? 'text-gray-400' : 'text-gray-600')}>
            {formatDistanceToNow(new Date(notification.timestamp), { addSuffix: true })}
          </span>
          <NotificationTypeBadge type={notification.notification_type} />
          {notification.urgent && (
            <AlertCircle className="h-4 w-4 text-red-500 shrink-0" aria-label="Urgent" />
          )}
          {isTruncatable && (
            <span className="ml-auto text-gray-400">
              {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </span>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}
