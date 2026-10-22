import { render, screen, fireEvent } from '@testing-library/react';
import { NotificationTypeFilter } from '../NotificationTypeFilter';
import type { NotificationType } from '@/types/notifications';
import { NOTIFICATION_TYPE_GROUPS } from '@/constants/notifications';

function renderFilter(
  selected: NotificationType[] = [],
  onChange: (types: NotificationType[]) => void = jest.fn()
) {
  return render(<NotificationTypeFilter selected={selected} onChange={onChange} />);
}

function openPopover() {
  fireEvent.click(screen.getByTestId('type-filter-trigger'));
}

describe('NotificationTypeFilter', () => {
  // ── Trigger label ──────────────────────────────────────────────────────────

  it('shows "All types" when nothing is selected', () => {
    renderFilter([]);
    expect(screen.getByTestId('type-filter-trigger')).toHaveTextContent('All types');
  });

  it('shows the group name when a group is selected', () => {
    renderFilter(['pipeline', 'schema_change']);
    expect(screen.getByTestId('type-filter-trigger')).toHaveTextContent('Data & pipeline');
  });

  it('shows "All types" for partial/custom selections not matching any group', () => {
    renderFilter(['pipeline']);
    expect(screen.getByTestId('type-filter-trigger')).toHaveTextContent('All types');
  });

  // ── Popover content ────────────────────────────────────────────────────────

  it('shows "All types" option with checkmark when nothing selected', () => {
    renderFilter([]);
    openPopover();
    expect(screen.getByTestId('type-filter-all')).toBeInTheDocument();
    expect(screen.getByTestId('type-filter-all')).toHaveTextContent('All types');
  });

  it('lists all group options in the popover', () => {
    renderFilter([]);
    openPopover();
    for (const group of NOTIFICATION_TYPE_GROUPS) {
      expect(screen.getByText(group.label)).toBeInTheDocument();
      expect(screen.getByText(group.subtitle)).toBeInTheDocument();
    }
  });

  it('calls onChange with group types when a group is clicked', () => {
    const onChange = jest.fn();
    renderFilter([], onChange);
    openPopover();

    fireEvent.click(screen.getByTestId('type-filter-group-data-pipeline'));
    expect(onChange).toHaveBeenCalledWith(['pipeline', 'schema_change']);
  });

  it('calls onChange([]) when "All types" is clicked', () => {
    const onChange = jest.fn();
    renderFilter(['pipeline', 'schema_change'], onChange);
    openPopover();

    fireEvent.click(screen.getByTestId('type-filter-all'));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it('switches group when a different group is clicked', () => {
    const onChange = jest.fn();
    renderFilter(['pipeline', 'schema_change'], onChange);
    openPopover();

    fireEvent.click(screen.getByTestId('type-filter-group-collaboration'));
    expect(onChange).toHaveBeenCalledWith(['sharing', 'access', 'mention']);
  });

  it('calls onChange with platform group types', () => {
    const onChange = jest.fn();
    renderFilter([], onChange);
    openPopover();

    fireEvent.click(screen.getByTestId('type-filter-group-platform'));
    expect(onChange).toHaveBeenCalledWith(['platform', 'announcement']);
  });
});
