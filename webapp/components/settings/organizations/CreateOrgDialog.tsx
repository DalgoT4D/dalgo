'use client';

import { useState } from 'react';
import { trackEvent } from '@/lib/analytics';
import { ANALYTICS_EVENTS, TRIAL_INVITE_SOURCES } from '@/constants/analytics';
import { BASE_PLANS } from '@/components/admin/constants';
import { FREE_TRIAL_PLAN_NAME } from '@/constants/trial';
import { TrialSignupInviteForm } from '@/components/trial/TrialSignupInviteForm';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useOrganizationActions } from '@/hooks/api/useUserManagement';
import { useAuthStore } from '@/stores/authStore';

interface CreateOrgDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DURATION_OPTIONS = [
  { value: 'Monthly', label: 'Monthly' },
  { value: 'Annual', label: 'Annual' },
  { value: 'Trial', label: 'Trial' },
];

const SUPERSET_OPTIONS = [
  { value: 'true', label: 'Yes' },
  { value: 'false', label: 'No' },
];

export function CreateOrgDialog({ open, onOpenChange }: CreateOrgDialogProps) {
  const { createOrganization } = useOrganizationActions();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    website: '',
    base_plan: '',
    subscription_duration: '',
    superset_included: '',
    start_date: '',
    end_date: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const { refreshOrganizations, setSelectedOrg } = useAuthStore();

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Organization name is required';
    }

    if (!formData.base_plan) {
      newErrors.base_plan = 'Plan type is required';
    }

    if (!formData.subscription_duration) {
      newErrors.subscription_duration = 'Billing frequency is required';
    }

    if (!formData.superset_included) {
      newErrors.superset_included = 'Please select if Superset is included';
    }

    if (
      formData.website &&
      !/^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$/.test(formData.website)
    ) {
      newErrors.website = 'Please enter a valid website URL';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) return;

    setIsSubmitting(true);
    try {
      const payload = {
        name: formData.name.trim(),
        website: formData.website.trim() || undefined,
        base_plan: formData.base_plan,
        subscription_duration: formData.subscription_duration,
        superset_included: formData.superset_included === 'true',
        can_upgrade_plan: formData.superset_included === 'false',
        start_date: formData.start_date || undefined,
        end_date: formData.end_date || undefined,
      };

      const response = await createOrganization(payload);
      trackEvent(ANALYTICS_EVENTS.ORG_CREATED);

      handleClose();
      await refreshOrganizations()
        .then(() => {
          if (response?.slug) {
            setSelectedOrg(response.slug);
          }
          window.location.reload();
        })
        .catch(() => {
          // refreshOrganizations failed, org switch skipped
        });
    } catch {
      // Error is handled in the hook
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    setFormData({
      name: '',
      website: '',
      base_plan: '',
      subscription_duration: '',
      superset_included: '',
      start_date: '',
      end_date: '',
    });
    setErrors({});
    onOpenChange(false);
  };

  const updateField = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: '' }));
    }
  };

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      handleClose();
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="sm:max-w-[500px] max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create Organization</DialogTitle>
          <DialogDescription>
            Create a new organization to manage your data and team.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label htmlFor="base_plan">Plan Type *</Label>
          <Select
            value={formData.base_plan}
            onValueChange={(value) => updateField('base_plan', value)}
          >
            <SelectTrigger
              id="base_plan"
              className={errors.base_plan ? 'border-red-500' : ''}
              data-testid="create-org-dialog-plan-select"
            >
              <SelectValue placeholder="Select plan type" />
            </SelectTrigger>
            <SelectContent>
              {BASE_PLANS.map((plan) => (
                <SelectItem key={plan} value={plan}>
                  {plan}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {errors.base_plan && <p className="text-sm text-red-500">{errors.base_plan}</p>}
        </div>

        {formData.base_plan === FREE_TRIAL_PLAN_NAME ? (
          <TrialSignupInviteForm source={TRIAL_INVITE_SOURCES.HEADER} onDone={handleClose} />
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Organization Name *</Label>
              <Input
                id="name"
                data-testid="create-org-dialog-name-input"
                value={formData.name}
                onChange={(e) => updateField('name', e.target.value)}
                placeholder="Enter organization name"
                className={errors.name ? 'border-red-500' : ''}
              />
              {errors.name && <p className="text-sm text-red-500">{errors.name}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="website">Website (Optional)</Label>
              <Input
                id="website"
                data-testid="create-org-dialog-website-input"
                type="url"
                value={formData.website}
                onChange={(e) => updateField('website', e.target.value)}
                placeholder="https://your-organization.org"
                className={errors.website ? 'border-red-500' : ''}
              />
              {errors.website && <p className="text-sm text-red-500">{errors.website}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="subscription_duration">Billing Frequency *</Label>
              <Select
                value={formData.subscription_duration}
                onValueChange={(value) => updateField('subscription_duration', value)}
              >
                <SelectTrigger
                  className={errors.subscription_duration ? 'border-red-500' : ''}
                  data-testid="create-org-dialog-billing-select"
                >
                  <SelectValue placeholder="Select billing frequency" />
                </SelectTrigger>
                <SelectContent>
                  {DURATION_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.subscription_duration && (
                <p className="text-sm text-red-500">{errors.subscription_duration}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="superset_included">Is Superset Included? *</Label>
              <Select
                value={formData.superset_included}
                onValueChange={(value) => updateField('superset_included', value)}
              >
                <SelectTrigger
                  className={errors.superset_included ? 'border-red-500' : ''}
                  data-testid="create-org-dialog-superset-select"
                >
                  <SelectValue placeholder="Select option" />
                </SelectTrigger>
                <SelectContent>
                  {SUPERSET_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.superset_included && (
                <p className="text-sm text-red-500">{errors.superset_included}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="start_date">Start Date</Label>
              <Input
                id="start_date"
                data-testid="create-org-dialog-start-date-input"
                type="date"
                value={formData.start_date}
                onChange={(e) => updateField('start_date', e.target.value)}
                className={errors.start_date ? 'border-red-500' : ''}
              />
              {errors.start_date && <p className="text-sm text-red-500">{errors.start_date}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="end_date">End Date</Label>
              <Input
                id="end_date"
                data-testid="create-org-dialog-end-date-input"
                type="date"
                value={formData.end_date}
                onChange={(e) => updateField('end_date', e.target.value)}
                className={errors.end_date ? 'border-red-500' : ''}
              />
              {errors.end_date && <p className="text-sm text-red-500">{errors.end_date}</p>}
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={handleClose}
                disabled={isSubmitting}
                data-testid="create-org-dialog-cancel"
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting} data-testid="create-org-dialog-submit">
                {isSubmitting ? 'Creating...' : 'Create Organization'}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
