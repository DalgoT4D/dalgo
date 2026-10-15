'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
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
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAdminOrg, useAdminOrgActions, type AdminOrg } from '@/hooks/api/useAdminPortal';
import { OrgUsersTable } from '@/components/admin/OrgUsersTable';
import { OrgFlagsPanel } from '@/components/admin/OrgFlagsPanel';
import { DeleteOrgDialog } from '@/components/admin/DeleteOrgDialog';
import { trackEvent, trackFeatureView } from '@/lib/analytics';
import { ANALYTICS_EVENTS, FEATURES } from '@/constants/analytics';
import { isValidVizUrl, VIZ_URL_ERROR } from '@/components/admin/utils';

const BASE_PLANS = ['Free Trial', 'Dalgo', 'Internal'];

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b py-3 last:border-b-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{children}</span>
    </div>
  );
}

interface OrgFormState {
  name: string;
  vizUrl: string;
  basePlan: string;
  supersetIncluded: string;
  subscriptionDuration: string;
  startDate: string;
  endDate: string;
}

interface OrgFormErrors {
  name?: string;
  vizUrl?: string;
  startDate?: string;
  endDate?: string;
}

interface OrgEditFormProps {
  org: AdminOrg;
  form: OrgFormState;
  errors: OrgFormErrors;
  saving: boolean;
  onChange: (patch: Partial<OrgFormState>) => void;
  onSave: () => void;
  onCancel: () => void;
}

function OrgEditForm({ org, form, errors, saving, onChange, onSave, onCancel }: OrgEditFormProps) {
  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <Label htmlFor="edit-name">Name</Label>
        <Input
          id="edit-name"
          value={form.name}
          onChange={(e) => onChange({ name: e.target.value })}
          className={errors.name ? 'border-destructive' : ''}
        />
        {errors.name && <p className="text-sm text-destructive">{errors.name}</p>}
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-slug">Slug</Label>
        <Input id="edit-slug" value={org.slug ?? ''} disabled />
        <p className="text-xs text-muted-foreground">
          Slug is locked after creation (it&apos;s used in URLs and Airbyte).
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-base-plan">Plan</Label>
        <Select value={form.basePlan} onValueChange={(v) => onChange({ basePlan: v })}>
          <SelectTrigger id="edit-base-plan">
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
      <div className="space-y-2">
        <Label htmlFor="edit-subscription-duration">Billing Frequency</Label>
        <Select
          value={form.subscriptionDuration}
          onValueChange={(v) => onChange({ subscriptionDuration: v })}
        >
          <SelectTrigger id="edit-subscription-duration">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="Monthly">Monthly</SelectItem>
            <SelectItem value="Annual">Annual</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {form.basePlan === 'Free Trial' && (
        <>
          <div className="space-y-2">
            <Label htmlFor="edit-start-date">Start Date</Label>
            <Input
              id="edit-start-date"
              type="date"
              value={form.startDate}
              onChange={(e) => onChange({ startDate: e.target.value })}
              className={errors.startDate ? 'border-destructive' : ''}
            />
            {errors.startDate && <p className="text-sm text-destructive">{errors.startDate}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-end-date">End Date</Label>
            <Input
              id="edit-end-date"
              type="date"
              value={form.endDate}
              onChange={(e) => onChange({ endDate: e.target.value })}
              className={errors.endDate ? 'border-destructive' : ''}
            />
            {errors.endDate && <p className="text-sm text-destructive">{errors.endDate}</p>}
          </div>
        </>
      )}
      <div className="space-y-2">
        <Label htmlFor="edit-superset-included">Superset Included</Label>
        <Select
          value={form.supersetIncluded}
          onValueChange={(v) =>
            onChange({ supersetIncluded: v, vizUrl: v === 'false' ? '' : form.vizUrl })
          }
        >
          <SelectTrigger id="edit-superset-included">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="false">No</SelectItem>
            <SelectItem value="true">Yes</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {form.supersetIncluded === 'true' && (
        <div className="space-y-2">
          <Label htmlFor="edit-viz-url">Visualization URL</Label>
          <Input
            id="edit-viz-url"
            type="url"
            value={form.vizUrl}
            onChange={(e) => onChange({ vizUrl: e.target.value })}
            placeholder="https://superset.example.org"
            className={errors.vizUrl ? 'border-destructive' : ''}
            data-testid="edit-org-viz-url-input"
          />
          {errors.vizUrl && <p className="text-sm text-destructive">{errors.vizUrl}</p>}
        </div>
      )}
      <div className="flex gap-3">
        <Button onClick={onSave} disabled={saving}>
          {saving ? 'Saving…' : 'Save changes'}
        </Button>
        <Button variant="outline" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function OrgReadView({ org }: { org: AdminOrg }) {
  return (
    <div>
      <Fact label="Name">{org.name}</Fact>
      <Fact label="Slug">{org.slug ?? '—'}</Fact>
      <Fact label="Plan">{org.base_plan ?? '—'}</Fact>
      <Fact label="Billing Frequency">{org.subscription_duration ?? '—'}</Fact>
      <Fact label="Superset Included">{org.superset_included ? 'Yes' : 'No'}</Fact>
      {org.superset_included && <Fact label="Visualization URL">{org.viz_url ?? '—'}</Fact>}
      {org.base_plan === 'Free Trial' && (
        <>
          <Fact label="Start Date">{org.start_date ? org.start_date.slice(0, 10) : '—'}</Fact>
          <Fact label="End Date">{org.end_date ? org.end_date.slice(0, 10) : '—'}</Fact>
        </>
      )}
      <Fact label="Users">{org.user_count}</Fact>
    </div>
  );
}

function orgToForm(org: AdminOrg): OrgFormState {
  return {
    name: org.name,
    vizUrl: org.viz_url ?? '',
    basePlan: org.base_plan ?? 'Free Trial',
    supersetIncluded: org.superset_included ? 'true' : 'false',
    subscriptionDuration: org.subscription_duration ?? 'Monthly',
    startDate: org.start_date ? org.start_date.slice(0, 10) : '',
    endDate: org.end_date ? org.end_date.slice(0, 10) : '',
  };
}

export default function AdminOrganizationDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const orgId = Number(params.id);
  const { org, isLoading, mutate } = useAdminOrg(Number.isNaN(orgId) ? null : orgId);
  const { updateOrg } = useAdminOrgActions();

  const [activeTab, setActiveTab] = useState('overview');
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<OrgFormState>(
    orgToForm({ superset_included: false } as AdminOrg)
  );
  const [errors, setErrors] = useState<OrgFormErrors>({});
  const [saving, setSaving] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  useEffect(() => {
    if (org) setForm(orgToForm(org));
  }, [org]);

  if (isLoading) {
    return (
      <div className="p-8">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="mt-6 h-64 w-full max-w-xl" />
      </div>
    );
  }

  if (!org) {
    return (
      <div className="p-8">
        <p className="text-muted-foreground">Organization not found.</p>
        <Link href="/admin/organizations" className="mt-2 inline-block text-sm underline">
          Back to organizations
        </Link>
      </div>
    );
  }

  const onSave = async () => {
    const trimmedName = form.name.trim();
    const trimmedVizUrl = form.vizUrl.trim();
    const nextErrors: OrgFormErrors = {};
    if (!trimmedName) nextErrors.name = 'Name is required';
    if (trimmedVizUrl && !isValidVizUrl(trimmedVizUrl)) nextErrors.vizUrl = VIZ_URL_ERROR;
    if (form.basePlan === 'Free Trial' && !form.startDate)
      nextErrors.startDate = 'Start date is required for trial accounts';
    if (form.basePlan === 'Free Trial' && !form.endDate)
      nextErrors.endDate = 'End date is required for trial accounts';
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setSaving(true);
    try {
      await updateOrg(org.id, {
        name: trimmedName,
        viz_url: trimmedVizUrl || undefined,
        base_plan: form.basePlan,
        superset_included: form.supersetIncluded === 'true',
        subscription_duration: form.subscriptionDuration,
        start_date: form.startDate || undefined,
        end_date: form.endDate || undefined,
      });
      trackEvent(ANALYTICS_EVENTS.ADMIN_ORG_UPDATED, { base_plan: form.basePlan });
      await mutate();
      setEditing(false);
    } catch {
      // toast already surfaced
    } finally {
      setSaving(false);
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

      <div className="mb-6 flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">{org.name}</h1>
        <div className="flex gap-2">
          {!editing && (
            <>
              <Button
                variant="outline"
                data-testid="edit-org-button"
                onClick={() => {
                  setActiveTab('overview');
                  setErrors({});
                  setEditing(true);
                }}
              >
                Edit
              </Button>
              <Button
                variant="destructive"
                data-testid="delete-org-button"
                onClick={() => setDeleteDialogOpen(true)}
              >
                Delete organization
              </Button>
            </>
          )}
        </div>
      </div>

      <Tabs
        value={activeTab}
        onValueChange={(value) => {
          setActiveTab(value);
          trackFeatureView(FEATURES.ADMIN_ORGANIZATIONS, { tab: value });
        }}
      >
        <TabsList>
          <TabsTrigger value="overview" data-testid="org-tab-overview">
            Overview
          </TabsTrigger>
          <TabsTrigger value="users" data-testid="org-tab-users">
            Users
          </TabsTrigger>
          <TabsTrigger value="flags" data-testid="org-tab-flags">
            Feature flags
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6">
          <Card className="max-w-xl">
            <CardHeader>
              <CardTitle>Overview</CardTitle>
            </CardHeader>
            <CardContent>
              {editing ? (
                <OrgEditForm
                  org={org}
                  form={form}
                  errors={errors}
                  saving={saving}
                  onChange={(patch) => setForm((f) => ({ ...f, ...patch }))}
                  onSave={onSave}
                  onCancel={() => {
                    setErrors({});
                    setForm(orgToForm(org));
                    setEditing(false);
                  }}
                />
              ) : (
                <OrgReadView org={org} />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="users" className="mt-6">
          <OrgUsersTable orgId={org.id} />
        </TabsContent>

        <TabsContent value="flags" className="mt-6">
          <OrgFlagsPanel orgId={org.id} />
        </TabsContent>
      </Tabs>

      <DeleteOrgDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        org={org}
        onSuccess={() => router.push('/admin/organizations')}
      />
    </div>
  );
}
