'use client';

import { Check, Filter } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import { NOTIFICATION_TYPE_GROUPS } from '@/constants/notifications';
import type { NotificationType } from '@/types/notifications';

interface NotificationTypeFilterProps {
  selected: NotificationType[];
  onChange: (types: NotificationType[]) => void;
}

function getActiveGroup(selected: NotificationType[]) {
  if (selected.length === 0) return null;
  return (
    NOTIFICATION_TYPE_GROUPS.find(
      (g) => g.types.length === selected.length && g.types.every((t) => selected.includes(t))
    ) ?? null
  );
}

function triggerLabel(selected: NotificationType[]): string {
  if (selected.length === 0) return 'All types';
  const group = getActiveGroup(selected);
  return group ? group.label : 'All types';
}

export function NotificationTypeFilter({ selected, onChange }: NotificationTypeFilterProps) {
  const activeGroup = getActiveGroup(selected);
  const hasSelection = selected.length > 0;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          data-testid="type-filter-trigger"
          className={cn(
            'flex items-center gap-1.5 px-1 py-2.5 text-sm font-medium cursor-pointer',
            hasSelection ? 'text-teal-600' : 'text-gray-500 hover:text-gray-700'
          )}
        >
          <Filter className="h-3.5 w-3.5 shrink-0" />
          <span>{triggerLabel(selected)}</span>
        </button>
      </PopoverTrigger>

      <PopoverContent align="end" className="w-56 p-2">
        <p className="text-xs text-gray-400 uppercase tracking-wide px-2 pb-1.5">Filter by type</p>

        <button
          data-testid="type-filter-all"
          onClick={() => onChange([])}
          className={cn(
            'flex w-full items-center justify-between rounded px-2 py-2 text-sm cursor-pointer hover:bg-accent',
            !activeGroup && 'bg-primary/5'
          )}
        >
          <span className={cn(!activeGroup ? 'text-primary font-medium' : 'text-foreground')}>
            All types
          </span>
          {!activeGroup && <Check className="h-4 w-4 text-primary" />}
        </button>

        {NOTIFICATION_TYPE_GROUPS.map((group) => {
          const isActive = activeGroup?.label === group.label;
          return (
            <button
              key={group.label}
              data-testid={`type-filter-group-${group.label.toLowerCase().replace(/[\s&]+/g, '-')}`}
              onClick={() => onChange(group.types)}
              className={cn(
                'flex w-full items-center justify-between rounded px-2 py-2 text-sm cursor-pointer hover:bg-accent',
                isActive && 'bg-primary/5'
              )}
            >
              <div className="text-left">
                <p className={cn(isActive ? 'text-primary font-medium' : 'text-foreground')}>
                  {group.label}
                </p>
                <p className="text-xs text-gray-400">{group.subtitle}</p>
              </div>
              {isActive && <Check className="h-4 w-4 text-primary shrink-0" />}
            </button>
          );
        })}
      </PopoverContent>
    </Popover>
  );
}
