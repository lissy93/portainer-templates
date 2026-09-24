import { error } from '@sveltejs/kit';
import { loadTemplates, getServices, mergeEnv } from '$lib/server/templates';
import { getDockerHubStats, getDockerMeta } from '$lib/server/dockerhub';
import { getGhcrStats } from '$lib/server/ghcr';
import { getIssuesUrl, getProjectStats, getReadme, getReleases } from '$lib/server/github';
import { cachedSearchIndex } from '$lib/server/search-index';
import { searchEntries } from '$lib/search';
import { listingTitle, slugify } from '$lib/format';
import { MODE_ORDER, groupKey, onePerApp, primarySlugs } from '$lib/server/variants';
import { getStatuses, statusOf } from '$lib/server/overrides';
import type { Template, Service, SimilarApp, DockerMeta, ProjectStats, SearchEntry, DeployMode } from '$src/Types';
import type { PageServerLoad } from './$types';

type Fetch = typeof globalThis.fetch;

/* Based on the current page name, find the corresponding template */
const findTemplate = (allTemplates: Template[], slug: string) => {
  return allTemplates.find((temp) => slugify(temp.title) === slug);
};

/* The deploy methods this app ships as (container/stack/swarm), for the mode switcher */
const findModes = (allTemplates: Template[], current: Template): DeployMode[] => {
  const key = groupKey(current.title);
  const currentSlug = slugify(current.title);
  const seen = new Set<number>();
  return allTemplates
    .filter((t) => groupKey(t.title) === key)
    .map((t) => ({ type: t.type, slug: slugify(t.title) }))
    .filter((m) => m.slug && !seen.has(m.type) && seen.add(m.type))
    .sort((a, b) => MODE_ORDER.indexOf(a.type) - MODE_ORDER.indexOf(b.type))
    .map((m) => ({ ...m, current: m.slug === currentSlug }));
};

/* Slim a template down to the fields the search results list needs (no third-party stats) */
const toSearchEntry = (t: Template): SearchEntry => ({
  slug: slugify(t.title),
  title: t.title,
  description: t.description ?? '',
  type: t.type,
  ...(t.logo && { logo: t.logo }),
  ...(t.categories?.length && { categories: t.categories }),
  ...(t.platform && { platform: t.platform }),
  ...(t.image && { image: t.image }),
});

/* Entries to search when a slug 404s: the prebuilt index for stats if it's ready, else the plain list */
const fallbackEntries = (allTemplates: Template[], primaries: Map<string, string>): SearchEntry[] => {
  const seen = new Set<string>();
  const entries = cachedSearchIndex()?.entries ?? allTemplates.map(toSearchEntry).filter((e) => e.slug && !seen.has(e.slug) && seen.add(e.slug));
  return onePerApp(entries, primaries, (e) => e.slug);
};

/* Match docker tags to github releases, so each version can show its release notes */
const withReleaseNotes = async (meta: DockerMeta | null, project: ProjectStats | null, fetch: Fetch): Promise<DockerMeta | null> => {
  if (!meta?.versions.length || !project) return meta;
  const releases = (await getReleases(project.repo, fetch)) ?? [];
  const bare = (tag: string) => tag.replace(/^v/i, '');
  const byTag = new Map(releases.map((rel) => [bare(rel.tag_name), rel]));
  const versions = meta.versions.map((version) => {
    const rel = byTag.get(bare(version.name));
    return rel ? { ...version, release: { title: rel.name, notes: rel.body, url: rel.html_url } } : version;
  });
  return { ...meta, versions };
};

/* Other apps sharing a category, A-Z, one per app. Local data, so it's cheap and always there. */
const findSimilar = (allTemplates: Template[], current: Template, primaries: Map<string, string>, limit = 12): SimilarApp[] => {
  const cats = new Set(current.categories ?? []);
  if (!cats.size) return [];
  const shared = (t: Template) => (t.categories ?? []).filter((c) => cats.has(c)).length;
  const key = groupKey(current.title);
  return onePerApp(allTemplates, primaries, (t) => slugify(t.title))
    .filter((t) => groupKey(t.title) !== key && shared(t) > 0)
    .sort((a, b) => shared(b) - shared(a) || a.title.localeCompare(b.title))
    .slice(0, limit)
    .map((t) => ({
      title: listingTitle(t.title, t.primary),
      slug: slugify(t.title),
      logo: t.logo,
      category: (t.categories ?? []).find((c) => cats.has(c)),
    }));
};

/* Format results for returning to component */
const returnResults = async (allTemplates: Template[], templateSlug: string, fetch: Fetch) => {
  // Started early, as it may fetch stackfiles on a cold start
  const primariesLookup = primarySlugs(allTemplates);

  // Find template, based on slug
  let template = findTemplate(allTemplates, templateSlug);
  if (!template) {
    // No such page. If the slug reads like a search, 404 but carry the results it would've matched
    const query = templateSlug.replace(/[-_]+/g, ' ');
    const matches = searchEntries(fallbackEntries(allTemplates, await primariesLookup), query, 24);
    throw error(404, matches.length ? { message: `No template named "${templateSlug}"`, query, matches } : `No template named "${templateSlug}"`);
  }

  // Fetch service info from associated stackfile, if it exists
  let { services, stackfile } = await getServices(template, fetch);

  // If only 1 service, merge it with the template, keeping the template's richer env defs
  if (services.length === 1) {
    template = { ...template, ...services[0], env: mergeEnv(template.env, services[0].env) };
  } else if (services.length > 1) {
    // If made up from multiple services, fetch Docker info for each image
    services = await Promise.all(
      services.map(async (service) => ({
        ...service,
        dockerStats: (await getDockerHubStats(service.image, fetch)) ?? (await getGhcrStats(service.image, fetch))?.info ?? null,
      }))
    );
  }

  // Everything below is independent, so fetch it all at once
  const [hubStats, hubMeta, project, ghcr, issuesUrl, statuses] = await Promise.all([
    getDockerHubStats(template.image, fetch),
    getDockerMeta(template.image, fetch, 30),
    getProjectStats(template, fetch),
    getGhcrStats(template.image, fetch),
    getIssuesUrl(template, fetch),
    getStatuses(),
  ]);
  // GHCR images aren't on Docker Hub, so fall back to the registry manifest for their image card
  const dockerStats = hubStats ?? ghcr?.info ?? null;
  const dockerMeta = await withReleaseNotes(hubMeta ?? ghcr?.meta ?? null, project, fetch);

  // No Docker Hub docs to show? Fall back to the project's GitHub readme
  const hasDocs = !!dockerStats?.full_description || services.some((s) => s.dockerStats?.full_description);
  const readme = !hasDocs && project ? await getReadme(project.repo, fetch) : null;

  return {
    template,
    dockerStats,
    dockerMeta,
    project,
    readme,
    services,
    stackfile,
    issuesUrl,
    status: statusOf(statuses, template) ?? null,
    similar: findSimilar(allTemplates, template, await primariesLookup),
    modes: findModes(allTemplates, template),
  };
};

export const load: PageServerLoad = async ({ params, fetch, setHeaders }) => {
  const list = await loadTemplates(fetch);
  // Third-party stats change slowly, so let CDNs and browsers hang onto the page
  setHeaders({ 'cache-control': 'public, max-age=600, s-maxage=3600, stale-while-revalidate=86400' });
  return returnResults(list, params.slug, fetch);
};
