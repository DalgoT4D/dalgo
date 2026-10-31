'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowUpDown, ChevronDown, ChevronUp, Plus, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';
// Cross-feature import on purpose, as in BroadcastHistory: TablePagination is presentational.
import { TablePagination } from '@/components/notifications/TablePagination';
import { useAdminOrgs, type AdminOrg } from '@/hooks/api/useAdminPortal';
import { ALL_PLANS_FILTER, BASE_PLANS } from '@/components/admin/constants';
import { DEFAULT_PAGE_SIZE } from '@/constants/notifications';

type OrgSortColumn = 'name' | 'slug' | 'plan' | 'users';
type SortOrder = 'asc' | 'desc';

const ORG_COLUMNS: {
  key: OrgSortColumn;
  label: string;
  sortValue: (org: AdminOrg) => string | number;
}[] = [
  { key: 'name', label: 'Name', sortValue: (org) => org.name.toLowerCase() },
  { key: 'slug', label: 'Slug', sortValue: (org) => (org.slug ?? '').toLowerCase() },
  { key: 'plan', label: 'Plan', sortValue: (org) => org.base_plan ?? '' },
  { key: 'users', label: 'Users', sortValue: (org) => org.user_count },
];

function SortIcon({ active, order }: { active: boolean; order: SortOrder }) {
  if (!active) return <ArrowUpDown className="h-4 w-4 text-muted-foreground" />;
  return order === 'asc' ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />;
}

export default function AdminOrganizationsPage() {
  const router = useRouter();
  const { orgs, isLoading } = useAdminOrgs();
  const [search, setSearch] = useState('');
  const [planFilter, setPlanFilter] = useState(ALL_PLANS_FILTER);
  const [sortBy, setSortBy] = useState<OrgSortColumn>('name');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

  const handleSort = (column: OrgSortColumn) => {
    if (column === sortBy) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('asc');
    }
    setPage(1);
  };

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (orgs ?? []).filter((org) => {
      const matchesPlan = planFilter === ALL_PLANS_FILTER || org.base_plan === planFilter;
      const matchesSearch =
        !term ||
        org.name.toLowerCase().includes(term) ||
        (org.slug ?? '').toLowerCase().includes(term);
      return matchesPlan && matchesSearch;
    });
  }, [orgs, search, planFilter]);

  const sorted = useMemo(() => {
    const { sortValue } = ORG_COLUMNS.find((column) => column.key === sortBy)!;
    const direction = sortOrder === 'asc' ? 1 : -1;
    return [...filtered].sort((a, b) => {
      const av = sortValue(a);
      const bv = sortValue(b);
      return (av < bv ? -1 : av > bv ? 1 : 0) * direction;
    });
  }, [filtered, sortBy, sortOrder]);

  const pageRows = sorted.slice((page - 1) * pageSize, page * pageSize);

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Organizations</h1>
          <p className="text-sm text-muted-foreground">Onboard and manage NGO organizations</p>
        </div>
        <Button asChild>
          <Link href="/admin/organizations/new">
            <Plus className="mr-2 h-4 w-4" />
            Create organization
          </Link>
        </Button>
      </div>

      <div className="mb-4 flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by name or slug"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="pl-9"
          />
        </div>
        <Select
          value={planFilter}
          onValueChange={(value) => {
            setPlanFilter(value);
            setPage(1);
          }}
        >
          <SelectTrigger
            id="admin-org-plan-filter"
            aria-label="Filter by plan"
            data-testid="admin-org-plan-filter"
            className="w-44"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_PLANS_FILTER}>All plans</SelectItem>
            {BASE_PLANS.map((plan) => (
              <SelectItem key={plan} value={plan}>
                {plan}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {ORG_COLUMNS.map((column) => (
                <TableHead key={column.key}>
                  <Button
                    variant="ghost"
                    className="h-auto p-0 font-medium hover:bg-transparent"
                    onClick={() => handleSort(column.key)}
                    data-testid={`admin-org-sort-${column.key}`}
                  >
                    <span className="flex items-center gap-2">
                      {column.label}
                      <SortIcon active={sortBy === column.key} order={sortOrder} />
                    </span>
                  </Button>
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              Array.from({ length: 3 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell colSpan={4}>
                    <Skeleton className="h-6 w-full" />
                  </TableCell>
                </TableRow>
              ))
            ) : filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="py-10 text-center text-muted-foreground">
                  No organizations found.
                </TableCell>
              </TableRow>
            ) : (
              pageRows.map((org) => (
                // The whole row is the target (any cell is a fine place to click), so it
                // carries the link semantics rather than the name cell — with keyboard
                // equivalents, since a TableRow is not focusable on its own.
                <TableRow
                  key={org.id}
                  role="link"
                  tabIndex={0}
                  aria-label={`Open ${org.name}`}
                  data-testid={`admin-org-row-${org.id}`}
                  className="cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={() => router.push(`/admin/organizations/${org.id}`)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault(); // Space would otherwise scroll the page
                      router.push(`/admin/organizations/${org.id}`);
                    }
                  }}
                >
                  <TableCell className="font-medium">{org.name}</TableCell>
                  <TableCell className="text-muted-foreground">{org.slug}</TableCell>
                  <TableCell>{org.base_plan ?? '—'}</TableCell>
                  <TableCell>{org.user_count}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {!isLoading && sorted.length > 0 && (
        <div className="mt-4">
          <TablePagination
            count={sorted.length}
            page={page}
            pageSize={pageSize}
            onPageChange={setPage}
            onPageSizeChange={(size) => {
              setPageSize(size);
              setPage(1);
            }}
          />
        </div>
      )}
    </div>
  );
}
