import { apiPublicPost } from '@/lib/api';
import { TRIAL_SIGNUP_PATH } from '@/constants/trial';
import type { TrialSignupRequest, TrialSignupResponse } from '@/types/trial';

/** Start a free trial: emails the verification link. Also re-sends it for an unverified email. */
export async function sendTrialSignup(data: TrialSignupRequest): Promise<TrialSignupResponse> {
  return (await apiPublicPost(TRIAL_SIGNUP_PATH, data)) as TrialSignupResponse;
}
