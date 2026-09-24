import { getSearchIndex } from '$lib/server/search-index';
import { loadTemplates } from '$lib/server/templates';
import { primarySlugs, tagPrimary } from '$lib/server/variants';
import type { PageServerLoad } from './$types';

export const prerender = true;

export const load: PageServerLoad = async ({ fetch }) => {
  const [index, templates] = await Promise.all([getSearchIndex(), loadTemplates(fetch)]);
  const primaries = await primarySlugs(templates);
  return { ...index, entries: tagPrimary(index.entries, primaries, (e) => e.slug) };
};
