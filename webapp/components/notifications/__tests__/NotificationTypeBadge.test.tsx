import { render, screen } from '@testing-library/react';
import { NotificationTypeBadge } from '../NotificationTypeBadge';
import type { NotificationType } from '@/types/notifications';
import { NOTIFICATION_TYPE_LABELS } from '@/constants/notifications';

describe('NotificationTypeBadge', () => {
  it('renders nothing when type is null', () => {
    const { container } = render(<NotificationTypeBadge type={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it.each(Object.entries(NOTIFICATION_TYPE_LABELS) as [NotificationType, string][])(
    'renders "%s" label for type "%s"',
    (type, label) => {
      render(<NotificationTypeBadge type={type} />);
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  );

  it('sets data-testid to notification-type-badge-{type}', () => {
    render(<NotificationTypeBadge type="pipeline" />);
    expect(screen.getByTestId('notification-type-badge-pipeline')).toBeInTheDocument();
  });

  it('applies teal brand styling classes', () => {
    const { container } = render(<NotificationTypeBadge type="platform" />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain('bg-primary/10');
    expect(badge.className).toContain('text-primary');
    expect(badge.className).toContain('border-primary/20');
  });

  it('appends extra className when provided', () => {
    const { container } = render(<NotificationTypeBadge type="sharing" className="mt-2" />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.className).toContain('mt-2');
  });
});
