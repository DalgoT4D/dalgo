'use client';

import { useState } from 'react';
import { Inbox, X } from 'lucide-react';
import type { Notification } from '@/types/notifications';
import { NotificationRow } from './NotificationRow';
import { TablePagination } from './TablePagination';
import { Skeleton } from '@/components/ui/skeleton';
import { Checkbox } from '@/components/ui/checkbox';
import { Table, TableBody, TableHead, TableHeader, TableRow } from '@/components/ui/table';

interface NotificationsListProps {
  notifications: Notification[];
  totalCount: number;
  selectedIds: number[];
  onSelectionChange: (ids: number[]) => void;
  onClearSelection: () => void;
  onMarkAsRead: () => void;
  onMarkAsUnread: () => void;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  isLoading?: boolean;
  isSelectAllMode?: boolean;
  onSelectAllPages?: () => void;
}

export function NotificationsList({
  notifications,
  totalCount,
  selectedIds,
  onSelectionChange,
  onClearSelection,
  onMarkAsRead,
  onMarkAsUnread,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  isLoading = false,
  isSelectAllMode = false,
  onSelectAllPages,
}: NotificationsListProps) {
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  const currentPageIds = new Set(notifications.map((n) => n.id));
  const selectedOnPage = selectedIds.filter((id) => currentPageIds.has(id));
  const allOnPageSelected =
    notifications.length > 0 && selectedOnPage.length === notifications.length;
  const allSelected = isSelectAllMode || allOnPageSelected;
  const someSelected =
    !isSelectAllMode && selectedOnPage.length > 0 && selectedOnPage.length < notifications.length;
  const showSelectAllPagesLink =
    allOnPageSelected && !isSelectAllMode && totalCount > notifications.length && onSelectAllPages;

  const handleSelectAll = (checked: boolean) => {
    if (!checked) {
      if (isSelectAllMode) {
        onClearSelection();
      } else {
        onSelectionChange([]);
      }
      return;
    }
    onSelectionChange(notifications.map((n) => n.id));
  };

  const handleSelectRow = (id: number, checked: boolean) => {
    if (checked) {
      onSelectionChange([...selectedIds, id]);
    } else {
      onSelectionChange(selectedIds.filter((selectedId) => selectedId !== id));
    }
  };

  const toggleExpand = (id: number) => {
    setExpandedRow(expandedRow === id ? null : id);
  };

  const hasSelection = isSelectAllMode || selectedIds.length > 0;

  if (isLoading) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex-1 overflow-auto px-6 pt-4">
          <div className="bg-white rounded-lg border shadow-sm">
            <div className="p-4 space-y-3">
              {Array.from({ length: 8 }, (_, i) => `skeleton-${i}`).map((key) => (
                <div key={key} className="flex items-center gap-4 py-4">
                  <Skeleton className="h-4 w-4 rounded" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-4 w-1/4" />
                  </div>
                  <Skeleton className="h-4 w-4 rounded-full" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Global empty state - no notifications at all
  if (totalCount === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 px-6 pt-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-gray-100">
          <Inbox className="h-8 w-8 text-gray-400" />
        </div>
        <div className="text-center">
          <h3 className="font-semibold text-gray-900 text-lg">No notifications</h3>
          <p className="text-sm text-gray-500 mt-1">
            You&apos;re all caught up! Check back later for new notifications.
          </p>
        </div>
      </div>
    );
  }

  // Current page is empty but notifications exist on other pages
  if (notifications.length === 0 && totalCount > 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 px-6 pt-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-gray-100">
          <Inbox className="h-8 w-8 text-gray-400" />
        </div>
        <div className="text-center">
          <h3 className="font-semibold text-gray-900 text-lg">No notifications on this page</h3>
          <p className="text-sm text-gray-500 mt-1">
            Try going back to the first page to see your notifications.
          </p>
          <button
            onClick={() => onPageChange(1)}
            className="mt-3 text-sm text-teal-600 hover:text-teal-700 font-medium"
          >
            Go to first page
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Table Container */}
      <div className="flex-1 overflow-hidden px-6 pt-4">
        <div className="h-full flex flex-col bg-white rounded-lg border shadow-sm">
          {/* Bulk Action Bar */}
          <div className="flex items-center justify-between px-4 py-3 border-b">
            <div className="flex items-center gap-3">
              <Checkbox
                data-testid="select-all-checkbox"
                checked={allSelected ? true : someSelected ? 'indeterminate' : false}
                onCheckedChange={handleSelectAll}
                aria-label="Select all notifications"
                className="border-gray-800 data-[state=checked]:bg-gray-900 data-[state=checked]:border-gray-900 data-[state=indeterminate]:bg-gray-600 data-[state=indeterminate]:border-gray-600"
              />
              {isSelectAllMode ? (
                <span className="text-sm font-medium text-gray-600">All {totalCount} selected</span>
              ) : hasSelection ? (
                <>
                  <span className="text-sm font-medium text-gray-600">
                    {selectedIds.length} selected
                  </span>
                  {showSelectAllPagesLink && (
                    <button
                      data-testid="select-all-pages-btn"
                      onClick={onSelectAllPages}
                      className="text-sm font-medium text-teal-600 hover:text-teal-700 cursor-pointer"
                    >
                      Select all {totalCount} across all pages
                    </button>
                  )}
                </>
              ) : (
                <>
                  <span className="text-sm font-medium text-gray-600">Select all</span>
                  <span className="text-gray-300">|</span>
                  <span className="text-sm font-medium text-gray-600">
                    Showing {notifications.length} of {totalCount} notifications
                  </span>
                </>
              )}
            </div>

            {hasSelection && (
              <div className="flex items-center gap-3 text-sm">
                <button
                  data-testid="mark-as-read-btn"
                  onClick={onMarkAsRead}
                  className="text-teal-600 hover:text-teal-700 font-medium cursor-pointer"
                >
                  Mark as read
                </button>
                <button
                  data-testid="mark-as-unread-btn"
                  onClick={onMarkAsUnread}
                  className="text-gray-600 hover:text-gray-800 font-medium cursor-pointer"
                >
                  Mark as unread
                </button>
                <button
                  data-testid="clear-selection-btn"
                  onClick={onClearSelection}
                  className="p-1 hover:bg-gray-100 rounded cursor-pointer"
                  aria-label="Clear selection"
                >
                  <X className="h-4 w-4 text-gray-400 hover:text-gray-600" />
                </button>
              </div>
            )}
          </div>

          {/* Scrollable Table */}
          <div
            className="flex-1 overflow-y-auto overflow-x-hidden"
            data-testid="notifications-table"
          >
            <Table>
              <TableHeader className="sr-only">
                <TableRow>
                  <TableHead>Select</TableHead>
                  <TableHead>Message</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {notifications.map((notification) => (
                  <NotificationRow
                    key={notification.id}
                    notification={notification}
                    isSelected={selectedIds.includes(notification.id)}
                    isExpanded={expandedRow === notification.id}
                    onSelect={handleSelectRow}
                    onToggleExpand={toggleExpand}
                  />
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Pagination Footer */}
          {totalCount > 0 && (
            <div className="flex-shrink-0">
              <TablePagination
                count={totalCount}
                page={page}
                pageSize={pageSize}
                onPageChange={onPageChange}
                onPageSizeChange={onPageSizeChange}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
