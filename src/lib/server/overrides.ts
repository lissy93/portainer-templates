import { cached } from './cache';
import { fetchJson } from './http';
import { groupKey } from './variants';
import { overridesUrl } from '$src/constants';
import type { Template, TemplateStatus } from '$src/Types';

const TTL_MS = 10 * 60_000;

const str = (value: unknown): string | undefined => (typeof value === 'string' ? value : undefined);

// Keyed like the aggregator: title without its variant suffix or punctuation, plus type (container by default)
const keyOf = (title: string, type: unknown) => `${groupKey(title)}:${Number(type) || 1}`;

/* Templates flagged in overrides.json as not working, empty if it can't be read */
export const getStatuses = async (): Promise<Map<string, TemplateStatus>> =>
  (await cached('overrides', TTL_MS, async () => {
    const data = await fetchJson<{ overrides?: Record<string, unknown>[] }>(overridesUrl);
    if (!Array.isArray(data?.overrides)) return null;
    return new Map(
      data.overrides.flatMap((o) => {
        const title = str(o?.title);
        const status = str(o?.status);
        return title && status ? [[keyOf(title, o.type), { status, note: str(o.note), updated: str(o.updated) }] as const] : [];
      }),
    );
  })) ?? new Map();

export const statusOf = (statuses: Map<string, TemplateStatus>, { title, type }: Pick<Template, 'title' | 'type'>) =>
  statuses.get(keyOf(title, type));
