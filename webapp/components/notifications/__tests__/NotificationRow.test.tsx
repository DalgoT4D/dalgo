import { render, screen, fireEvent } from '@testing-library/react';
import { NotificationRow } from '../NotificationRow';
import { createMockNotification, longMessage } from './notification-mock-data';

const mockNotification = createMockNotification();

function renderRow(props: Partial<React.ComponentProps<typeof NotificationRow>> = {}) {
  return render(
    <table>
      <tbody>
        <NotificationRow
          notification={mockNotification}
          isSelected={false}
          isExpanded={false}
          onSelect={jest.fn()}
          onToggleExpand={jest.fn()}
          {...props}
        />
      </tbody>
    </table>
  );
}

describe('NotificationRow', () => {
  it('renders notification message correctly', () => {
    renderRow();
    expect(screen.getByText(mockNotification.message)).toBeInTheDocument();
  });

  it('applies line-clamp-2 class when not expanded', () => {
    const longNotification = createMockNotification({ message: longMessage });
    const { container } = renderRow({ notification: longNotification });
    const messageEl = container.querySelector('.line-clamp-2');
    expect(messageEl).toBeInTheDocument();
  });

  it('removes line-clamp-2 class when expanded', () => {
    const longNotification = createMockNotification({ message: longMessage });
    const { container } = renderRow({ notification: longNotification, isExpanded: true });
    const messageEl = container.querySelector('.line-clamp-2');
    expect(messageEl).not.toBeInTheDocument();
  });

  it('shows expand chevron for long messages', () => {
    const longNotification = createMockNotification({ message: longMessage });
    const { container } = renderRow({ notification: longNotification });
    // ChevronDown is rendered as an svg inside a span when truncatable
    const row = container.querySelector(`[data-testid="notification-row-${longNotification.id}"]`);
    expect(row).toBeInTheDocument();
    // Lucide renders the icon; verify the span wrapper is there
    const chevronSpan = container.querySelector('.ml-auto');
    expect(chevronSpan).toBeInTheDocument();
  });

  it('does not show expand chevron for short messages', () => {
    const { container } = renderRow();
    const chevronSpan = container.querySelector('.ml-auto');
    expect(chevronSpan).not.toBeInTheDocument();
  });

  it('calls onToggleExpand when the row is clicked', () => {
    const onToggleExpand = jest.fn();
    const longNotification = createMockNotification({ message: longMessage });
    const { container } = renderRow({ notification: longNotification, onToggleExpand });
    const row = container.querySelector(`[data-testid="notification-row-${longNotification.id}"]`);
    fireEvent.click(row!);
    expect(onToggleExpand).toHaveBeenCalledWith(longNotification.id);
  });

  it('calls onSelect when checkbox is clicked and does not call onToggleExpand', () => {
    const onSelect = jest.fn();
    const onToggleExpand = jest.fn();
    renderRow({ onSelect, onToggleExpand });

    const checkbox = screen.getByRole('checkbox');
    fireEvent.click(checkbox);

    expect(onSelect).toHaveBeenCalledWith(mockNotification.id, true);
    // stopPropagation on the cell prevents the row expand handler from firing
    expect(onToggleExpand).not.toHaveBeenCalled();
  });

  it('displays urgent indicator for urgent notifications', () => {
    const urgentNotification = createMockNotification({ urgent: true });
    renderRow({ notification: urgentNotification });
    expect(screen.getByLabelText('Urgent')).toBeInTheDocument();
  });

  it('does not display urgent indicator for non-urgent notifications', () => {
    renderRow();
    expect(screen.queryByLabelText('Urgent')).not.toBeInTheDocument();
  });

  it('applies read styling for read notifications', () => {
    const readNotification = createMockNotification({ read_status: true });
    const { container } = renderRow({ notification: readNotification });
    expect(container.querySelector('.text-gray-500')).toBeInTheDocument();
  });

  it('applies unread styling for unread notifications', () => {
    const { container } = renderRow();
    expect(container.querySelector('.text-gray-800')).toBeInTheDocument();
  });

  it('formats timestamp as relative time', () => {
    renderRow();
    expect(screen.getByText(/ago/)).toBeInTheDocument();
  });

  it('renders links in messages as clickable anchors', () => {
    const notificationWithLink = createMockNotification({
      message: 'Check this link: https://example.com/test for more info',
    });
    renderRow({ notification: notificationWithLink });
    const link = screen.getByRole('link', { name: 'https://example.com/test' });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', 'https://example.com/test');
    expect(link).toHaveAttribute('target', '_blank');
  });

  // ── Notification type badge ────────────────────────────────────────────────

  it('renders a type badge when notification_type is set', () => {
    const typed = createMockNotification({ notification_type: 'pipeline' });
    renderRow({ notification: typed });
    expect(screen.getByTestId('notification-type-badge-pipeline')).toBeInTheDocument();
    expect(screen.getByText('Pipeline')).toBeInTheDocument();
  });

  it('renders no type badge when notification_type is null', () => {
    renderRow();
    // createMockNotification defaults to null
    expect(screen.queryByTestId(/notification-type-badge/)).not.toBeInTheDocument();
  });

  it('renders the correct label for each known type', () => {
    const types = [
      'sharing',
      'access',
      'mention',
      'schema_change',
      'pipeline',
      'platform',
      'announcement',
    ] as const;
    const labels: Record<string, string> = {
      sharing: 'Sharing',
      access: 'Access',
      mention: 'Mention',
      schema_change: 'Schema Change',
      pipeline: 'Pipeline',
      platform: 'Platform',
      announcement: 'Announcement',
    };

    for (const type of types) {
      const notification = createMockNotification({ id: 99, notification_type: type });
      const { unmount } = renderRow({ notification });
      expect(screen.getByText(labels[type])).toBeInTheDocument();
      unmount();
    }
  });
});
