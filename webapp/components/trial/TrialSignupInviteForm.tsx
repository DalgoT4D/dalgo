'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Button } from '@/components/ui/button';
import { TrialSignupFields } from '@/components/trial/TrialSignupFields';
import { sendTrialSignup } from '@/hooks/api/useTrialSignups';
import { toastError, toastInfo } from '@/lib/toast';
import { trackEvent } from '@/lib/analytics';
import { ANALYTICS_EVENTS, type TrialInviteSource } from '@/constants/analytics';
import { TRIAL_ACCOUNT_EXISTS_STATUS, TRIAL_PERIOD_DAYS } from '@/constants/trial';
import type { TrialSignupRequest } from '@/types/trial';

interface TrialSignupInviteFormProps {
  source: TrialInviteSource;
  onDone: () => void;
  doneLabel?: string;
}

/** Start a trial for someone else through the public signup: they get the verification email. */
export function TrialSignupInviteForm({
  source,
  onDone,
  doneLabel = 'Done',
}: TrialSignupInviteFormProps) {
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [resending, setResending] = useState(false);
  const {
    register,
    control,
    handleSubmit,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<TrialSignupRequest>();

  const onSubmit = async (data: TrialSignupRequest) => {
    try {
      await sendTrialSignup(data);
      trackEvent(ANALYTICS_EVENTS.TRIAL_INVITE_SENT, { source });
      setSentTo(data.email);
    } catch (error) {
      const message = error instanceof Error ? error.message : '';
      if (message.includes(String(TRIAL_ACCOUNT_EXISTS_STATUS))) {
        toastInfo.generic('An account with this email already exists.');
      } else {
        toastError.api(error, 'Could not start the trial. Please try again.');
      }
    }
  };

  // re-POSTing the same signup sends a fresh link for a not-yet-verified email
  const handleResend = async () => {
    if (resending) return;
    setResending(true);
    try {
      await sendTrialSignup(getValues());
      trackEvent(ANALYTICS_EVENTS.TRIAL_INVITE_RESENT, { source });
      toastInfo.generic(`Verification link re-sent to ${sentTo}.`);
    } catch (error) {
      toastError.api(error, 'Could not resend the link. Please try again.');
    } finally {
      setResending(false);
    }
  };

  if (sentTo) {
    return (
      <div className="space-y-4" data-testid="trial-invite-sent">
        <h3 className="text-xl font-semibold">Verification link sent</h3>
        <p className="text-sm text-muted-foreground">
          We&apos;ve sent a verification link to <strong>{sentTo}</strong>. They need to click it to
          set their password and create their workspace.
        </p>
        <p className="text-xs text-muted-foreground">
          Incorrect email?{' '}
          <button
            type="button"
            onClick={() => setSentTo(null)}
            className="font-medium text-primary underline hover:no-underline"
            data-testid="trial-invite-change-email"
          >
            Change email address
          </button>
        </p>
        <p className="text-xs text-muted-foreground">
          Didn&apos;t receive it?{' '}
          <button
            type="button"
            onClick={handleResend}
            disabled={resending}
            className="font-medium text-primary underline hover:no-underline disabled:opacity-50"
            data-testid="trial-invite-resend"
          >
            {resending ? 'Resending…' : 'Resend email'}
          </button>
        </p>
        <Button variant="primary" onClick={onDone} data-testid="trial-invite-done">
          {doneLabel}
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6" noValidate>
      <TrialSignupFields register={register} control={control} errors={errors} />
      <p className="text-xs text-muted-foreground" data-testid="trial-invite-period">
        Trial period: {TRIAL_PERIOD_DAYS} days, starting when they verify their email.
      </p>
      <Button
        type="submit"
        variant="primary"
        disabled={isSubmitting}
        data-testid="trial-invite-submit"
      >
        {isSubmitting ? 'Sending…' : 'Create organization'}
      </Button>
    </form>
  );
}
