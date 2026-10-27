'use client';

import { useState, useEffect } from 'react';
import { trackFeatureView } from '@/lib/analytics';
import { FEATURES } from '@/constants/analytics';
import { Settings } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { NotificationsList } from '@/components/notifications/NotificationsList';
import { NotificationPreferencesDialog } from '@/components/notifications/NotificationPreferencesDialog';
import { NotificationTypeFilter } from '@/components/notifications/NotificationTypeFilter';
import {
  useNotifications,
  useNotificationActions,
  useUnreadCount,
} from '@/hooks/api/useNotifications';
import { buildFilters } from '@/lib/notifications';
import type { NotificationTab, NotificationType } from '@/types/notifications';
import { DEFAULT_PAGE_SIZE, NOTIFICATION_TABS } from '@/constants/notifications';

const TAB_TRIGGER_CLASS =
  'relative bg-transparent border-0 shadow-none rounded-none px-1 py-2.5 text-sm font-medium uppercase tracking-wide text-gray-500 cursor-pointer data-[state=active]:text-teal-600 data-[state=active]:bg-transparent data-[state=active]:shadow-none after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-transparent data-[state=active]:after:bg-teal-600';

export default function NotificationsPage() {
  const [activeTab, setActiveTab] = useState<NotificationTab>('all');
  const [activeTypeFilters, setActiveTypeFilters] = useState<NotificationType[]>([]);
  const [showPreferences, setShowPreferences] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [isSelectAllMode, setIsSelectAllMode] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

  const { unreadCount, mutate: mutateUnreadCount } = useUnreadCount();
  const filters = buildFilters(activeTab, page, pageSize, {
    notification_types: activeTypeFilters.length > 0 ? activeTypeFilters : undefined,
  });
  const { notifications, totalCount, mutate, isLoading } = useNotifications(filters);
  const { markAsRead } = useNotificationActions();

  // Reset selection and page when tab or type filter changes
  useEffect(() => {
    setSelectedIds([]);
    setIsSelectAllMode(false);
    setPage(1);
  }, [activeTab, activeTypeFilters]);

  // Reset page when page size changes
  useEffect(() => {
    setPage(1);
  }, [pageSize]);

  const handleMarkAsRead = async () => {
    if (!isSelectAllMode && selectedIds.length === 0) return;
    const success = await markAsRead(selectedIds, true, isSelectAllMode);
    if (success) {
      await mutate();
      await mutateUnreadCount();
      setSelectedIds([]);
      setIsSelectAllMode(false);
    }
  };

  const handleMarkAsUnread = async () => {
    if (!isSelectAllMode && selectedIds.length === 0) return;
    const success = await markAsRead(selectedIds, false, isSelectAllMode);
    if (success) {
      await mutate();
      await mutateUnreadCount();
      setSelectedIds([]);
      setIsSelectAllMode(false);
    }
  };

  const handleTabChange = (value: string) => {
    setActiveTab(value as NotificationTab);
    trackFeatureView(FEATURES.NOTIFICATIONS, { tab: value });
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex-shrink-0 border-b bg-background">
        <div className="mb-6 p-6 pb-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold">Notifications</h1>
              {unreadCount > 0 && (
                <Badge
                  data-testid="unread-count-badge"
                  className="bg-teal-600 hover:bg-teal-600 text-white px-2.5 py-0.5 text-xs font-medium"
                >
                  {unreadCount}
                </Badge>
              )}
            </div>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setShowPreferences(true)}
                  className="h-11 w-11 text-gray-500 hover:text-gray-700 hover:bg-gray-100"
                  aria-label="Manage notification preferences"
                >
                  <Settings className="h-7 w-7" />
                </Button>
              </TooltipTrigger>
              <TooltipContent className="bg-gray-900 text-white border-gray-700">
                Manage Preferences
              </TooltipContent>
            </Tooltip>
          </div>
          <p className="text-muted-foreground mt-1">View and manage your notifications</p>
        </div>

        {/* Read/unread tabs + type filter */}
        <div className="px-6 flex items-center justify-between">
          <Tabs value={activeTab} onValueChange={handleTabChange}>
            <TabsList className="bg-transparent p-0 h-auto gap-4">
              {NOTIFICATION_TABS.map((tab) => (
                <TabsTrigger key={tab.value} value={tab.value} className={TAB_TRIGGER_CLASS}>
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          <NotificationTypeFilter selected={activeTypeFilters} onChange={setActiveTypeFilters} />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        <NotificationsList
          notifications={notifications}
          totalCount={totalCount}
          selectedIds={selectedIds}
          onSelectionChange={setSelectedIds}
          onClearSelection={() => {
            setSelectedIds([]);
            setIsSelectAllMode(false);
          }}
          onMarkAsRead={handleMarkAsRead}
          onMarkAsUnread={handleMarkAsUnread}
          page={page}
          pageSize={pageSize}
          onPageChange={(p) => {
            setPage(p);
            setSelectedIds([]);
            setIsSelectAllMode(false);
          }}
          onPageSizeChange={(s) => {
            setPageSize(s);
            setSelectedIds([]);
            setIsSelectAllMode(false);
          }}
          isLoading={isLoading}
          isSelectAllMode={isSelectAllMode}
          onSelectAllPages={() => setIsSelectAllMode(true)}
        />
      </div>

      <NotificationPreferencesDialog open={showPreferences} onOpenChange={setShowPreferences} />
    </div>
  );
}
