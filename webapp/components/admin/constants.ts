import { FREE_TRIAL_PLAN_NAME } from '@/constants/trial';

/**
 * Shared constants for the admin portal.
 *
 * EMAIL_RE is the portal's authoritative email check — the invite forms set
 * `noValidate` so the browser's native type=email check can't preempt our own error
 * messages, which makes this regex the only thing standing between a typo and a
 * bounced invitation.
 */
export const EMAIL_RE = /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i;

/** Plan-filter value meaning "don't filter by plan" on the Organizations list. */
export const ALL_PLANS_FILTER = 'all';

export const DALGO_PLAN_NAME = 'Dalgo';
export const INTERNAL_PLAN_NAME = 'Internal';

/** The org plans; must match the backend's OrgPlanType values. */
export const BASE_PLANS = [FREE_TRIAL_PLAN_NAME, DALGO_PLAN_NAME, INTERNAL_PLAN_NAME];
