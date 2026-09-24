import yaml from 'js-yaml';
import { cached } from './cache';
import { fetchText } from './http';
import { baseTitle, isHiddenVariant, slugify } from '$lib/format';
import type { Template } from '$src/Types';

const COUNT_TTL_MS = 6 * 3_600_000;

// Reading order for variants: container, stack, swarm, edge
export const MODE_ORDER = [1, 3, 2, 4];

// Same app minus its "(container)"/"(stack)"/etc suffix, so differently-worded variants still group
export const groupKey = (title: string): string => baseTitle(title).replace(/[^a-z0-9]/gi, '').toLowerCase();

// How many services a stack's compose file runs, null if unreadable
const countServices = ({ repository }: Template): Promise<number | null> => {
  if (!repository) return Promise.resolve(null);
  const raw = `${repository.url.replace('github.com', 'raw.githubusercontent.com')}/HEAD/${repository.stackfile}`;
  return cached(`services:${raw}`, COUNT_TTL_MS, async () => {
    const text = await fetchText(raw);
    try {
      return text ? Object.keys((yaml.load(text) as { services?: object } | null)?.services ?? {}).length : null;
    } catch {
      return null;
    }
  });
};

// Maps each variant's slug to the one listings show: the container, unless its stack runs several services
export async function primarySlugs(templates: Template[]): Promise<Map<string, string>> {
  const groups = new Map<string, Template[]>();
  for (const t of templates) {
    const key = groupKey(t.title);
    groups.set(key, [...(groups.get(key) ?? []), t]);
  }
  const primaries = new Map<string, string>();
  await Promise.all(
    [...groups.values()]
      .filter((group) => group.length > 1)
      .map(async (group) => {
        const [first] = [...group].sort((a, b) => MODE_ORDER.indexOf(a.type) - MODE_ORDER.indexOf(b.type));
        const stack = group.find((t) => t.type === 3);
        const pick = first.type === 1 && stack && ((await countServices(stack)) ?? 0) > 1 ? stack : first;
        for (const t of group) primaries.set(slugify(t.title), slugify(pick.title));
      }),
  );
  return primaries;
}

// Tags each variant with its app's primary slug
export const tagPrimary = <T extends { primary?: string }>(items: T[], primaries: Map<string, string>, slugOf: (item: T) => string): T[] =>
  items.map((item) => {
    const primary = primaries.get(slugOf(item));
    return primary ? { ...item, primary } : item;
  });

// Tagged items minus the variants their primary stands in for
export const onePerApp = <T extends { primary?: string }>(items: T[], primaries: Map<string, string>, slugOf: (item: T) => string): T[] =>
  tagPrimary(items, primaries, slugOf).filter((item) => !isHiddenVariant(slugOf(item), item.primary));
