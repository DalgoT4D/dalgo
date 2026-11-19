import { useEffect, useRef } from 'react';
import type { GeographicHierarchy } from '@/types/charts';

/** One region row from the map data overlay API (`data` array). */
export interface MapDataRow {
  name: string;
  value: number | null;
}

/**
 * Name of the only region that has data, or null.
 * The map-data-overlay API returns only regions that have rows, so any value —
 * including a real 0 or a negative — means the region is in the data.
 */
export function findSingleRegionWithData(rows: MapDataRow[] | undefined | null): string | null {
  if (!rows) return null;
  const withData = rows.filter((row) => row.value !== null && row.value !== undefined);
  return withData.length === 1 ? withData[0].name : null;
}

/** Auto drill-down needs the flag on and at least one drill-down level to drill into. */
export function isAutoDrillEnabled(hierarchy: GeographicHierarchy | undefined | null): boolean {
  return Boolean(
    hierarchy?.auto_drill_single_region && (hierarchy.drill_down_levels?.length ?? 0) > 0
  );
}

interface UseAutoDrillSingleRegionArgs {
  enabled: boolean;
  /** True when the map shows the base (country) level, i.e. not drilled down. */
  isAtBaseLevel: boolean;
  /** True once everything the drill handler needs (e.g. the regions list) has loaded. */
  canDrill: boolean;
  mapRows: MapDataRow[] | undefined | null;
  /** Identifies the base-level query (incl. filters). Changes re-arm the auto drill. */
  payloadKey: string;
  /** The render site's existing region-click drill handler. */
  drillInto: (regionName: string) => void;
}

/**
 * When enabled and the base-level map data has exactly one region with data,
 * drill into it — once per payloadKey, so drilling back up doesn't re-trigger it
 * until the filters change.
 */
export function useAutoDrillSingleRegion({
  enabled,
  isAtBaseLevel,
  canDrill,
  mapRows,
  payloadKey,
  drillInto,
}: UseAutoDrillSingleRegionArgs): void {
  const firedForKey = useRef<string | null>(null);

  useEffect(() => {
    if (!enabled || !isAtBaseLevel || !canDrill) return;
    if (firedForKey.current === payloadKey) return;

    const regionName = findSingleRegionWithData(mapRows);
    if (!regionName) return;

    firedForKey.current = payloadKey;
    drillInto(regionName);
  }, [enabled, isAtBaseLevel, canDrill, mapRows, payloadKey, drillInto]);
}
