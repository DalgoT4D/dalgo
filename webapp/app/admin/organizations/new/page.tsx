'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useAdminOrgActions } from '@/hooks/api/useAdminPortal';
import { BASE_PLANS, DALGO_PLAN_NAME, EMAIL_RE } from '@/components/admin/constants';
import { isValidVizUrl, VIZ_URL_ERROR } from '@/components/admin/utils';
import { TrialSignupInviteForm } from '@/components/trial/TrialSignupInviteForm';
import { trackEvent } from '@/lib/analytics';
import { ANALYTICS_EVENTS, TRIAL_INVITE_SOURCES } from '@/constants/analytics';
import { FREE_TRIAL_PLAN_NAME } from '@/constants/trial';

const DURATION_OPTIONS = ['Monthly', 'Annual', 'Trial'];

export default function AdminCreateOrganizationPage() {
  const router = useRouter();
  const { createOrg } = useAdminOrgActions();
  const [name, setName] = useState('');
  const [adminEmail, setAdminEmail] = useState('');
  const [vizUrl, setVizUrl] = useState('');
  // Dalgo by default: Free Trial emails a signup link, so it should be a deliberate choice
  const [basePlan, setBasePlan] = useState(DALGO_PLAN_NAME);
  const [subscriptionDuration, setSubscriptionDuration] = useState('Monthly');
  const [supersetIncluded, setSupersetIncluded] = useState('false');
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<{ name?: string; adminEmail?: string; vizUrl?: string }>({});

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const nextErrors: { name?: string; adminEmail?: string; vizUrl?: string } = {};
    if (!name.trim()) {
      nextErrors.name = 'Organization name is required';
    }
    if (!EMAIL_RE.test(adminEmail.trim())) {
      nextErrors.adminEmail = 'Invalid email address';
    }
    if (vizUrl.trim() && !isValidVizUrl(vizUrl.trim())) {
      nextErrors.vizUrl = VIZ_URL_ERROR;
    }
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setSubmitting(true);
    try {
      const org = await createOrg({
        name: name.trim(),
        viz_url: vizUrl.trim() || undefined,
        base_plan: basePlan,
        subscription_duration: subscriptionDuration,
        superset_included: supersetIncluded === 'true',
        can_upgrade_plan: supersetIncluded === 'false',
        admin_email: adminEmail.trim(),
      });
      trackEvent(ANALYTICS_EVENTS.ADMIN_ORG_CREATED, { base_plan: basePlan });
      router.push(`/admin/organizations/${org.id}`);
    } catch {
      // toast already surfaced by the action; stay on the form
      setSubmitting(false);
    }
  };

  return (
    <div className="p-8">
      <Link
        href="/admin/organizations"
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to organizations
      </Link>

      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>Create organization</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="org-base-plan">Plan</Label>
            <Select value={basePlan} onValueChange={setBasePlan}>
              <SelectTrigger id="org-base-plan" data-testid="org-base-plan-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {BASE_PLANS.map((plan) => (
                  <SelectItem key={plan} value={plan}>
                    {plan}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {basePlan === FREE_TRIAL_PLAN_NAME ? (
            <TrialSignupInviteForm
              source={TRIAL_INVITE_SOURCES.ADMIN_PORTAL}
              onDone={() => router.push('/admin/organizations')}
              doneLabel="Back to organizations"
            />
          ) : (
            <form onSubmit={onSubmit} className="space-y-5" noValidate>
              <div className="space-y-2">
                <Label htmlFor="org-name">Name</Label>
                <Input
                  id="org-name"
                  data-testid="org-name-input"
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value);
                    if (errors.name) setErrors((prev) => ({ ...prev, name: undefined }));
                  }}
                  placeholder="e.g. Bhumi"
                  className={errors.name ? 'border-destructive' : ''}
                />
                {errors.name && <p className="text-sm text-destructive">{errors.name}</p>}
                <p className="text-xs text-muted-foreground">
                  The slug is generated from the name and can&apos;t be changed later.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="org-admin-email">Admin email</Label>
                <Input
                  id="org-admin-email"
                  type="email"
                  value={adminEmail}
                  onChange={(e) => setAdminEmail(e.target.value)}
                  placeholder="user@example.com"
                  className={errors.adminEmail ? 'border-destructive' : ''}
                  data-testid="org-admin-email-input"
                  required
                />
                {errors.adminEmail && (
                  <p className="text-sm text-destructive">{errors.adminEmail}</p>
                )}
                <p className="text-xs text-muted-foreground">
                  They&apos;ll be invited as the organization&apos;s Admin and set their own
                  password. An organization can&apos;t be created without one.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="org-subscription-duration">Billing Frequency</Label>
                <Select value={subscriptionDuration} onValueChange={setSubscriptionDuration}>
                  <SelectTrigger id="org-subscription-duration" data-testid="org-billing-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DURATION_OPTIONS.map((d) => (
                      <SelectItem key={d} value={d}>
                        {d}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="org-superset-included">Superset Included</Label>
                <Select
                  value={supersetIncluded}
                  onValueChange={(v) => {
                    setSupersetIncluded(v);
                    if (v === 'false') setVizUrl('');
                  }}
                >
                  <SelectTrigger
                    id="org-superset-included"
                    data-testid="org-superset-included-select"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="false">No</SelectItem>
                    <SelectItem value="true">Yes</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {supersetIncluded === 'true' && (
                <div className="space-y-2">
                  <Label htmlFor="org-viz-url">Visualization URL (optional)</Label>
                  <Input
                    id="org-viz-url"
                    type="url"
                    value={vizUrl}
                    onChange={(e) => setVizUrl(e.target.value)}
                    placeholder="https://superset.example.org"
                    className={errors.vizUrl ? 'border-destructive' : ''}
                    data-testid="org-viz-url-input"
                  />
                  {errors.vizUrl && <p className="text-sm text-destructive">{errors.vizUrl}</p>}
                </div>
              )}

              <p className="text-xs text-muted-foreground">
                Creating an organization also provisions its Airbyte workspace, which can take a
                moment and may fail if Airbyte is unavailable.
              </p>

              <div className="flex gap-3">
                <Button
                  type="submit"
                  disabled={submitting || !adminEmail.trim()}
                  data-testid="create-org-submit"
                >
                  {submitting ? 'Creating...' : 'Create organization'}
                </Button>
                <Button type="button" variant="outline" asChild data-testid="create-org-cancel">
                  <Link href="/admin/organizations">Cancel</Link>
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
