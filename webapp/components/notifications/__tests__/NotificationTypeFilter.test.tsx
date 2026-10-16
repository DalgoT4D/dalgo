import { render, screen, fireEvent } from '@testing-library/react';
import { NotificationTypeFilter } from '../NotificationTypeFilter';
import type { NotificationType } from '@/types/notifications';
import { PERSONAL_NOTIFICATION_TYPES } from '@/constants/notifications';

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

  it('shows the type name when exactly one type is selected', () => {
    renderFilter(['pipeline']);
    expect(screen.getByTestId('type-filter-trigger')).toHaveTextContent('Pipeline');
  });

  it('shows "{N} types" when multiple types are selected', () => {
    renderFilter(['pipeline', 'sharing', 'access']);
    expect(screen.getByTestId('type-filter-trigger')).toHaveTextContent('3 types');
  });

  // ── Clear button ───────────────────────────────────────────────────────────

  it('does not show the clear button when nothing is selected', () => {
    renderFilter([]);
    expect(screen.queryByTestId('type-filter-clear')).not.toBeInTheDocument();
  });

  it('shows the clear button when at least one type is selected', () => {
    renderFilter(['pipeline']);
    expect(screen.getByTestId('type-filter-clear')).toBeInTheDocument();
  });

  it('calls onChange([]) when the clear button is clicked', () => {
    const onChange = jest.fn();
    renderFilter(['pipeline'], onChange);
    fireEvent.click(screen.getByTestId('type-filter-clear'));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  // ── Popover content ────────────────────────────────────────────────────────

  it('lists all personal notification types in the popover', () => {
    renderFilter([]);
    openPopover();
    for (const type of PERSONAL_NOTIFICATION_TYPES) {
      // Each type row has a Checkbox + label text; the label text is the human-readable name
      expect(screen.getByText(new RegExp(type.replace('_', ' '), 'i'))).toBeInTheDocument();
    }
  });

  it('adds a type to the selection when it is clicked', () => {
    const onChange = jest.fn();
    renderFilter([], onChange);
    openPopover();

    // Click the "Pipeline" row
    fireEvent.click(screen.getByText('Pipeline'));
    expect(onChange).toHaveBeenCalledWith(['pipeline']);
  });

  it('removes a type from the selection when a selected type is clicked again', () => {
    const onChange = jest.fn();
    // Use 2 selected so the trigger shows "2 types" (not "Pipeline"), avoiding
    // duplicate text matches when the popover is open.
    renderFilter(['pipeline', 'sharing'], onChange);
    openPopover();

    fireEvent.click(screen.getAllByText('Pipeline')[0]);
    expect(onChange).toHaveBeenCalledWith(['sharing']);
  });

  it('appends to existing selection when a new type is clicked', () => {
    const onChange = jest.fn();
    renderFilter(['sharing'], onChange);
    openPopover();

    fireEvent.click(screen.getByText('Pipeline'));
    expect(onChange).toHaveBeenCalledWith(['sharing', 'pipeline']);
  });
});
