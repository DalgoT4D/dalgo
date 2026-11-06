import { transformMapDataOverlayPayload, type MapDataOverlayRawPayload } from '../useChart';
import type { ChartFilter } from '@/types/charts';

const basePayload: MapDataOverlayRawPayload = {
  schema_name: 'public',
  table_name: 'visits',
  geographic_column: 'state',
  metric: { column: 'visit_id', aggregation: 'count', alias: 'count' },
};

const chartFilters: ChartFilter[] = [{ column: 'attended', operator: 'equals', value: 'no' }];

describe('transformMapDataOverlayPayload', () => {
  // The backend only reads chart filters from extra_config.filters
  it('sends builder chart filters as extra_config.filters', () => {
    const result = transformMapDataOverlayPayload({ ...basePayload, chart_filters: chartFilters });

    expect(result.extra_config.filters).toEqual(chartFilters);
  });
});
