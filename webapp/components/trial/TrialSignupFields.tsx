'use client';

import { Controller, type Control, type FieldErrors, type UseFormRegister } from 'react-hook-form';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { TrialField } from '@/app/free-trial/_components/TrialField';
import { EMAIL_RE } from '@/components/admin/constants';
import { WORK_FUNCTION_OPTIONS } from '@/constants/trial';
import type { TrialSignupRequest } from '@/types/trial';

interface TrialSignupFieldsProps {
  register: UseFormRegister<TrialSignupRequest>;
  control: Control<TrialSignupRequest>;
  errors: FieldErrors<TrialSignupRequest>;
}

/** The trial signup fields, shared by the public signup and the create-org forms. */
export function TrialSignupFields({ register, control, errors }: TrialSignupFieldsProps) {
  return (
    <div className="space-y-5">
      <TrialField id="email" label="Email ID" error={errors.email?.message}>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          placeholder="e.g. name@example.org"
          aria-invalid={!!errors.email}
          data-testid="trial-signup-email-input"
          {...register('email', {
            required: 'Required field',
            pattern: { value: EMAIL_RE, message: 'Invalid email. Please check again' },
          })}
        />
      </TrialField>

      <TrialField id="role" label="Function" error={errors.role?.message}>
        <Controller
          name="role"
          control={control}
          rules={{ required: 'Required field' }}
          render={({ field }) => (
            <Select value={field.value || ''} onValueChange={field.onChange}>
              <SelectTrigger
                id="role"
                className="w-full"
                aria-invalid={!!errors.role}
                data-testid="trial-signup-role-input"
              >
                <SelectValue placeholder="eg. Data and Technology" />
              </SelectTrigger>
              <SelectContent>
                {WORK_FUNCTION_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
      </TrialField>

      <TrialField id="org_name" label="Organization Name" error={errors.org_name?.message}>
        <Input
          id="org_name"
          type="text"
          autoComplete="organization"
          placeholder="eg. ABC foundation"
          aria-invalid={!!errors.org_name}
          data-testid="trial-signup-org-name-input"
          {...register('org_name', { required: 'Required field' })}
        />
      </TrialField>
    </div>
  );
}
