'use client';

import { Filter, X } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Checkbox } from '@/components/ui/checkbox';
import { cn } from '@/lib/utils';
import { NOTIFICATION_TYPE_LABELS, PERSONAL_NOTIFICATION_TYPES } from '@/constants/notifications';
import type { NotificationType } from '@/types/notifications';

interface NotificationTypeFilterProps {
  selected: NotificationType[];
  onChange: (types: NotificationType[]) => void;
}

function triggerLabel(selected: NotificationType[]): string {
  if (selected.length === 0) return 'All types';
  if (selected.length === 1) return NOTIFICATION_TYPE_LABELS[selected[0]];
  return `${selected.length} types`;
}

export function NotificationTypeFilter({ selected, onChange }: NotificationTypeFilterProps) {
  const hasSelection = selected.length > 0;

  const toggle = (type: NotificationType) => {
    if (selected.includes(type)) {
      onChange(selected.filter((t) => t !== type));
    } else {
      onChange([...selected, type]);
    }
  };

  const clear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange([]);
  };

  return (
    <div className="flex items-center gap-1">
      <Popover>
        <PopoverTrigger asChild>
          <button
            data-testid="type-filter-trigger"
            className={cn(
              'flex items-center gap-1.5 px-1 py-2.5 text-sm font-medium uppercase tracking-wide cursor-pointer',
              hasSelection ? 'text-teal-600' : 'text-gray-500 hover:text-gray-700'
            )}
          >
            <Filter className="h-3.5 w-3.5 shrink-0" />
            <span>{triggerLabel(selected)}</span>
          </button>
        </PopoverTrigger>

        <PopoverContent align="end" className="w-44 p-1">
          {PERSONAL_NOTIFICATION_TYPES.map((type) => {
            const checked = selected.includes(type);
            return (
              <button
                key={type}
                onClick={() => toggle(type)}
                className={cn(
                  'flex w-full items-center gap-2.5 rounded px-2 py-1.5 text-sm cursor-pointer hover:bg-accent',
                  checked && 'bg-primary/5'
                )}
              >
                <Checkbox
                  checked={checked}
                  className="pointer-events-none border-gray-300 data-[state=checked]:bg-primary data-[state=checked]:border-primary"
                />
                <span className={cn(checked ? 'text-primary font-medium' : 'text-foreground')}>
                  {NOTIFICATION_TYPE_LABELS[type]}
                </span>
              </button>
            );
          })}
        </PopoverContent>
      </Popover>

      {hasSelection && (
        <button
          onClick={clear}
          className="text-gray-400 hover:text-gray-600 cursor-pointer"
          aria-label="Clear type filter"
          data-testid="type-filter-clear"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
