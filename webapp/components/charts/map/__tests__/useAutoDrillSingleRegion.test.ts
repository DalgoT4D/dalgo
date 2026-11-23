import { renderHook } from '@testing-library/react';
import {
  findSingleRegionWithData,
  isAutoDrillEnabled,
  useAutoDrillSingleRegion,
  type MapDataRow,
} from '../useAutoDrillSingleRegion';
import type { GeographicHierarchy } from '@/types/charts';

// The map-data-overlay API only returns regions that have rows, so one row = one state
const singleStateRows: MapDataRow[] = [{ name: 'Tamil Nadu', value: 10 }];

const hierarchy = (overrides: Partial<GeographicHierarchy> = {}): GeographicHierarchy => ({
  country_code: 'IND',
  base_level: { level: 0, column: 'statename', region_type: 'state', label: 'State' },
  drill_down_levels: [
    { level: 1, column: 'districtname', region_type: 'district', label: 'District' },
  ],
  ...overrides,
});

describe('findSingleRegionWithData', () => {
  it('returns the name when exactly one region has data', () => {
    expect(findSingleRegionWithData(singleStateRows)).toBe('Tamil Nadu');
  });

  // e.g. last month's enrollment = 0 — the state is in the data, so it counts
  it('counts a region whose value is a real zero', () => {
    expect(findSingleRegionWithData([{ name: 'Kerala', value: 0 }])).toBe('Kerala');
  });

  it('counts a region with a negative value', () => {
    expect(findSingleRegionWithData([{ name: 'Kerala', value: -12 }])).toBe('Kerala');
  });

  it('returns null when two regions have data, even if one is zero', () => {
    expect(
      findSingleRegionWithData([
        { name: 'Kerala', value: 0 },
        { name: 'Tamil Nadu', value: 500 },
      ])
    ).toBeNull();
  });

  it('ignores rows without a value', () => {
    expect(
      findSingleRegionWithData([
        { name: 'Kerala', value: 7 },
        { name: 'Goa', value: null },
      ])
    ).toBe('Kerala');
  });

  it('returns null when no region has data', () => {
    expect(findSingleRegionWithData([])).toBeNull();
  });

  it('returns null for missing rows', () => {
    expect(findSingleRegionWithData(undefined)).toBeNull();
    expect(findSingleRegionWithData(null)).toBeNull();
  });
});

describe('isAutoDrillEnabled', () => {
  it('is false without drill-down levels even if the flag is set', () => {
    expect(
      isAutoDrillEnabled(hierarchy({ auto_drill_single_region: true, drill_down_levels: [] }))
    ).toBe(false);
  });

  it('is true with the flag and a drill-down level', () => {
    expect(isAutoDrillEnabled(hierarchy({ auto_drill_single_region: true }))).toBe(true);
  });

  it('is false when the flag is missing', () => {
    expect(isAutoDrillEnabled(hierarchy())).toBe(false);
    expect(isAutoDrillEnabled(undefined)).toBe(false);
  });
});

describe('useAutoDrillSingleRegion', () => {
  const baseProps = {
    enabled: true,
    isAtBaseLevel: true,
    canDrill: true,
    mapRows: singleStateRows,
    payloadKey: 'payload-1',
  };

  it('drills once into the single region', () => {
    const drillInto = jest.fn();
    const { rerender } = renderHook((props) => useAutoDrillSingleRegion(props), {
      initialProps: { ...baseProps, drillInto },
    });
    rerender({ ...baseProps, drillInto });

    expect(drillInto).toHaveBeenCalledTimes(1);
    expect(drillInto).toHaveBeenCalledWith('Tamil Nadu');
  });

  it('does nothing when disabled', () => {
    const drillInto = jest.fn();
    renderHook(() => useAutoDrillSingleRegion({ ...baseProps, enabled: false, drillInto }));
    expect(drillInto).not.toHaveBeenCalled();
  });

  it('waits until regions are ready', () => {
    const drillInto = jest.fn();
    const { rerender } = renderHook((props) => useAutoDrillSingleRegion(props), {
      initialProps: { ...baseProps, canDrill: false, drillInto },
    });
    expect(drillInto).not.toHaveBeenCalled();

    rerender({ ...baseProps, canDrill: true, drillInto });
    expect(drillInto).toHaveBeenCalledTimes(1);
  });

  it('does not drill when already drilled down', () => {
    const drillInto = jest.fn();
    renderHook(() => useAutoDrillSingleRegion({ ...baseProps, isAtBaseLevel: false, drillInto }));
    expect(drillInto).not.toHaveBeenCalled();
  });

  it('does not re-drill after the user returns to the base level with the same data', () => {
    const drillInto = jest.fn();
    const { rerender } = renderHook((props) => useAutoDrillSingleRegion(props), {
      initialProps: { ...baseProps, drillInto },
    });
    rerender({ ...baseProps, isAtBaseLevel: false, drillInto });
    rerender({ ...baseProps, isAtBaseLevel: true, drillInto });

    expect(drillInto).toHaveBeenCalledTimes(1);
  });

  it('drills again when the payload (filters) changes', () => {
    const drillInto = jest.fn();
    const { rerender } = renderHook((props) => useAutoDrillSingleRegion(props), {
      initialProps: { ...baseProps, drillInto },
    });
    rerender({ ...baseProps, payloadKey: 'payload-2', drillInto });

    expect(drillInto).toHaveBeenCalledTimes(2);
  });

  it('does not drill when several regions have data', () => {
    const drillInto = jest.fn();
    renderHook(() =>
      useAutoDrillSingleRegion({
        ...baseProps,
        mapRows: [
          { name: 'Tamil Nadu', value: 10 },
          { name: 'Kerala', value: 5 },
        ],
        drillInto,
      })
    );
    expect(drillInto).not.toHaveBeenCalled();
  });
});
