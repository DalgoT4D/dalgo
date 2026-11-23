/**
 * TrialSignupInviteForm — starting a trial for someone else runs the public signup.
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TrialSignupInviteForm } from '../TrialSignupInviteForm';
import { sendTrialSignup } from '@/hooks/api/useTrialSignups';
import { TRIAL_INVITE_SOURCES } from '@/constants/analytics';

jest.mock('@/hooks/api/useTrialSignups');
jest.mock('@/lib/analytics', () => ({ trackEvent: jest.fn() }));

it('sends the same signup as the public form, then shows the verification-sent message', async () => {
  (sendTrialSignup as jest.Mock).mockResolvedValue({ status: 'verification_sent' });
  const user = userEvent.setup({ delay: null });
  render(<TrialSignupInviteForm source={TRIAL_INVITE_SOURCES.ADMIN_PORTAL} onDone={jest.fn()} />);

  await user.type(screen.getByTestId('trial-signup-email-input'), 'owner@bhumi.org');
  await user.click(screen.getByTestId('trial-signup-role-input'));
  await user.click(await screen.findByRole('option', { name: 'Data and Technology' }));
  await user.type(screen.getByTestId('trial-signup-org-name-input'), 'Bhumi');
  await user.click(screen.getByTestId('trial-invite-submit'));

  await waitFor(() =>
    expect(sendTrialSignup).toHaveBeenCalledWith({
      email: 'owner@bhumi.org',
      role: 'data_technology',
      org_name: 'Bhumi',
    })
  );
  expect(await screen.findByTestId('trial-invite-sent')).toHaveTextContent('owner@bhumi.org');
});
