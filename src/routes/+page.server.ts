import { error } from '@sveltejs/kit';
import { get } from 'svelte/store';
import { templates } from '$src/store';
import { templatesUrl } from '$src/constants';
import { onePerApp, primarySlugs } from '$lib/server/variants';
import { getStatuses, statusOf } from '$lib/server/overrides';
import { slugify } from '$lib/format';
import type { Template, TemplateCard, TemplateStatus } from '$src/Types';
import type { PageServerLoad } from './$types';

const makeCategories = (allTemplates: TemplateCard[]): Record<string, number> => {
  // Get categories from templates
  const categories = allTemplates.reduce((acc: Record<string, number>, { categories: templateCategories }) => {
    (templateCategories || []).forEach((category) => {
      acc[category] = (acc[category] || 0) + 1;
    });
    return acc;
  }, {});

  // Sort categories by count, and remove categories with only a few templates
  const sortedCategories = Object.fromEntries(
    Object.entries(categories)
      .filter(([, value]) => value > 3)
      .sort(([, a], [, b]) => b - a)
  );

  return sortedCategories;
};

/* One card per app, so container/stack variants don't list twice */
const makeListing = async (allTemplates: Template[], statuses: Map<string, TemplateStatus>) => {
  const cards: TemplateCard[] = allTemplates.map((t) => {
    const status = statusOf(statuses, t)?.status;
    return { title: t.title, description: t.description, logo: t.logo, categories: t.categories, ...(status && { status }) };
  });
  const listed = onePerApp(cards, await primarySlugs(allTemplates), (t) => slugify(t.title));
  return { templates: listed, categories: makeCategories(listed), total: allTemplates.length };
};

export const load: PageServerLoad = async () => {
  const statusLookup = getStatuses();
  try {
    const data = await fetch(templatesUrl).then((res) => res.json());
    templates.set(data.templates);
    return await makeListing(data.templates, await statusLookup);
  } catch {
    // On a fetch failure, fall back to the last successfully loaded list if we have one
    const cached = get(templates);
    if (cached.length) return makeListing(cached, await statusLookup);
    throw error(503, 'Could not load the templates list. Please try again shortly.');
  }
};
