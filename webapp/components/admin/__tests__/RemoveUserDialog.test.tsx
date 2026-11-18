/**
 * RemoveUserDialog — the safety guardrail for the destructive, cascading remove
 * action. The non-negotiable requirement (plan.md §4.6): the real removal-impact
 * counts MUST be fetched and shown BEFORE the user can confirm removal. These
 * tests prove the confirm cannot fire without the impact data present.
 */

import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RemoveUserDialog } from '@/components/admin/RemoveUserDialog';
import * as useAdminPortal from '@/hooks/api/useAdminPortal';
import { ANALYTICS_EVENTS } from '@/constants/analytics';

jest.mock('@/hooks/api/useAdminPortal');

const mockTrackEvent = jest.fn();
jest.mock('@/lib/analytics', () => ({
  trackEvent: (...args: unknown[]) => mockTrackEvent(...args),
}));

const mockRemoveUser = jest.fn().mockResolvedValue(undefined);
const mockGetRemovalImpact = useAdminPortal.getRemovalImpact as jest.Mock;

const orgUser = {
  orguser_id: 7,
  email: 'priya@akshara.org',
  new_role_slug: 'guest',
};

const newOwner = { orguser_id: 11, email: 'admin@akshara.org', new_role_slug: 'admin' };

async function pickNewOwner() {
  await userEvent.click(screen.getByTestId('admin-remove-new-owner-select'));
  await userEvent.click(await screen.findByRole('option', { name: newOwner.email }));
}

beforeEach(() => {
  jest.clearAllMocks();
  mockRemoveUser.mockResolvedValue(undefined);
  (useAdminPortal.useAdminOrgUserActions as jest.Mock).mockReturnValue({
    removeUser: mockRemoveUser,
    inviteUser: jest.fn(),
    changeRole: jest.fn(),
    cancelInvitation: jest.fn(),
  });
});

function renderDialog() {
  return render(
    <RemoveUserDialog
      open
      onOpenChange={jest.fn()}
      orgId={42}
      orgUser={orgUser}
      onSuccess={jest.fn()}
    />
  );
}

describe('RemoveUserDialog', () => {
  it('fetches and displays the real removal-impact counts when opened', async () => {
    mockGetRemovalImpact.mockResolvedValue({
      dashboards_orphaned: 3,
      charts_orphaned: 5,
      reports_orphaned: 2,
    });

    renderDialog();

    expect(mockGetRemovalImpact).toHaveBeenCalledWith(42, 7);
    await waitFor(() => expect(screen.getByTestId('removal-impact-summary')).toBeInTheDocument());
    expect(screen.getByTestId('removal-impact-dashboards').textContent).toContain('3');
    expect(screen.getByTestId('removal-impact-charts').textContent).toContain('5');
    expect(screen.getByTestId('removal-impact-reports').textContent).toContain('2');
  });

  it('CANNOT submit removal while the impact is still loading (confirm disabled, no call)', async () => {
    // a promise that never resolves — impact never arrives
    mockGetRemovalImpact.mockReturnValue(new Promise(() => {}));

    renderDialog();

    const confirm = screen.getByTestId('remove-user-confirm');
    expect(confirm).toBeDisabled();
    // even a forced click must not trigger the removal
    fireEvent.click(confirm);
    expect(mockRemoveUser).not.toHaveBeenCalled();
  });

  it('CANNOT submit removal if the impact fetch fails (confirm stays disabled, no call)', async () => {
    mockGetRemovalImpact.mockRejectedValue(new Error('network down'));

    renderDialog();

    await waitFor(() => expect(screen.getByTestId('removal-impact-error')).toBeInTheDocument());
    const confirm = screen.getByTestId('remove-user-confirm');
    expect(confirm).toBeDisabled();
    fireEvent.click(confirm);
    expect(mockRemoveUser).not.toHaveBeenCalled();
  });

  it('allows removal only after the counts are shown and a new owner is picked', async () => {
    mockGetRemovalImpact.mockResolvedValue({
      dashboards_orphaned: 1,
      charts_orphaned: 0,
      reports_orphaned: 0,
      new_owner_options: [newOwner],
    });

    renderDialog();

    // wait until the impact summary is on screen; confirm still needs a new owner
    await waitFor(() => expect(screen.getByTestId('removal-impact-summary')).toBeInTheDocument());
    const confirm = screen.getByTestId('remove-user-confirm');
    expect(confirm).toBeDisabled();

    await pickNewOwner();
    expect(confirm).toBeEnabled();

    await userEvent.click(confirm);
    expect(mockRemoveUser).toHaveBeenCalledWith(42, 7, newOwner.orguser_id);
  });

  it('blocks removal when the org has no admin to take over the content', async () => {
    mockGetRemovalImpact.mockResolvedValue({
      dashboards_orphaned: 1,
      charts_orphaned: 0,
      reports_orphaned: 0,
      new_owner_options: [],
    });

    renderDialog();

    await waitFor(() => expect(screen.getByTestId('removal-no-new-owner')).toBeInTheDocument());
    expect(screen.getByTestId('remove-user-confirm')).toBeDisabled();
  });

  it('reports the removal with the orphan counts and no email', async () => {
    mockGetRemovalImpact.mockResolvedValue({
      dashboards_orphaned: 1,
      charts_orphaned: 4,
      reports_orphaned: 0,
      new_owner_options: [newOwner],
    });

    renderDialog();

    await waitFor(() => expect(screen.getByTestId('removal-impact-summary')).toBeInTheDocument());
    await pickNewOwner();
    await userEvent.click(screen.getByTestId('remove-user-confirm'));

    await waitFor(() =>
      expect(mockTrackEvent).toHaveBeenCalledWith(ANALYTICS_EVENTS.ADMIN_USER_REMOVED, {
        dashboards_orphaned: 1,
        charts_orphaned: 4,
        reports_orphaned: 0,
      })
    );
    expect(JSON.stringify(mockTrackEvent.mock.calls)).not.toContain('priya@akshara.org');
  });

  it('does not report a removal that failed', async () => {
    mockGetRemovalImpact.mockResolvedValue({
      dashboards_orphaned: 0,
      charts_orphaned: 0,
      reports_orphaned: 0,
      new_owner_options: [newOwner],
    });
    mockRemoveUser.mockRejectedValueOnce(new Error('backend down'));

    renderDialog();

    await waitFor(() => expect(screen.getByTestId('removal-impact-summary')).toBeInTheDocument());
    await pickNewOwner();
    await userEvent.click(screen.getByTestId('remove-user-confirm'));

    await waitFor(() => expect(mockRemoveUser).toHaveBeenCalled());
    expect(mockTrackEvent).not.toHaveBeenCalled();
  });
});
