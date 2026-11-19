import { renderHook, waitFor } from '@testing-library/react';
import { useAllSchemaTables } from '../useChart';
import { mockApiGet } from '@/test-utils/api';
import { TestWrapper } from '@/test-utils/render';

const httpError = (status: number, message: string) =>
  Object.assign(new Error(message), { status });

describe('useAllSchemaTables', () => {
  beforeEach(() => {
    mockApiGet.mockReset();
  });

  // The dataset list comes straight from the warehouse, so it must not depend on
  // /api/organizations/warehouses (which calls Airbyte and 500s when Airbyte is down).
  it('loads tables from sync_tables without calling the Airbyte-backed warehouses endpoint', async () => {
    mockApiGet.mockImplementation(async (url: string) => {
      if (url.startsWith('/api/warehouse/sync_tables')) {
        return [{ schema: 'public', name: 'users', type: 'source' }];
      }
      throw httpError(500, 'Airbyte down');
    });

    const { result } = renderHook(() => useAllSchemaTables(), { wrapper: TestWrapper });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.data).toEqual([
      { schema_name: 'public', table_name: 'users', full_name: 'public.users' },
    ]);
    expect(result.current.noWarehouse).toBe(false);
    expect(result.current.error).toBeFalsy();
    expect(mockApiGet).not.toHaveBeenCalledWith('/api/organizations/warehouses');
  });

  it('reports noWarehouse (not an error) when sync_tables returns 404', async () => {
    mockApiGet.mockRejectedValue(httpError(404, 'Please set up your warehouse first'));

    const { result } = renderHook(() => useAllSchemaTables(), { wrapper: TestWrapper });

    await waitFor(() => expect(result.current.noWarehouse).toBe(true));
    expect(result.current.error).toBeFalsy();
    expect(result.current.data).toEqual([]);
  });

  it('surfaces other sync_tables failures as an error', async () => {
    mockApiGet.mockRejectedValue(httpError(500, 'Failed to fetch data from the warehouse'));

    const { result } = renderHook(() => useAllSchemaTables(), { wrapper: TestWrapper });

    await waitFor(() => expect(result.current.error).toBeTruthy());
    expect(result.current.noWarehouse).toBe(false);
  });
});
