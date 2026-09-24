import { env } from '$env/dynamic/private';
import { cached } from './cache';
import { fetchJson, fetchText } from './http';
import { baseTitle } from '$lib/format';
import type { ProjectStats, Template } from '$src/Types';

const DAY = 86_400_000;

// Grab owner/repo from a github link. repo is greedy over word/dot/dash chars, so it
// naturally stops at the next slash, bracket or space (handles trailing slashes too).
const GITHUB_LINK = /\bgithub\.com\/([\w.-]+)\/([\w.-]+)/gi;
// A project's Pages site (owner.github.io/repo) maps straight back to its repo.
const PAGES_LINK = /\b([\w-]+)\.github\.io\/([\w.-]+)/i;
const NOT_A_PROJECT = new Set(['sponsors', 'orgs', 'apps', 'topics', 'about', 'features', 'marketplace']);
// Owners that republish other people's apps; their repos aren't the upstream project.
const AGGREGATORS = new Set(['linuxserver']);
// Monorepos that bundle many apps; not any single upstream project.
const AGGREGATOR_REPOS = new Set(['pi-hosted/pi-hosted']);

function toRepo(owner: string, repo: string): string | null {
  const o = owner.toLowerCase();
  const name = repo.replace(/\.git$/i, '').replace(/\.+$/, '');
  if (!name || NOT_A_PROJECT.has(o) || AGGREGATORS.has(o)) return null;
  if (AGGREGATOR_REPOS.has(`${o}/${name.toLowerCase()}`)) return null;
  return `${owner}/${name}`;
}

// Repos a template might map to, strongest signal first. Each is checked against the
// GitHub API in turn, so a wrong guess costs one 404 and falls through to the next.
// Aggregators (linuxserver on lscr.io etc) yield no candidate, so they never match.
export function candidateRepos({ description, note, image }: Pick<Template, 'description' | 'note' | 'image'>): string[] {
  const text = `${description ?? ''} ${note ?? ''}`;
  const gh = [...text.matchAll(GITHUB_LINK)].map((m) => toRepo(m[1], m[2]));
  const pages = text.match(PAGES_LINK);
  const img = (image ?? '').split('@')[0].split(':')[0].split('/');
  const ghcr = img.length === 3 && img[0] === 'ghcr.io' ? img.slice(1) : null;
  const hub = img.length === 2 && !img[0].includes('.') ? img : null;

  const ordered = [
    ...gh,                               // explicit github links, the most deliberate signal
    ghcr && toRepo(ghcr[0], ghcr[1]),    // a GHCR image lives in the repo's own namespace
    pages && toRepo(pages[1], pages[2]), // the project's Pages site maps back to its repo
    hub && toRepo(hub[0], hub[1]),       // docker hub owner often mirrors the repo
  ];
  return [...new Set(ordered.filter((r): r is string => !!r))];
}

function httpsOnly(url?: string | null): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' ? parsed.href : null;
  } catch {
    return null;
  }
}

interface GhRepo {
  stargazers_count: number;
  forks_count: number;
  language: string | null;
  pushed_at: string;
  homepage: string | null;
  archived: boolean;
  license: { spdx_id: string | null } | null;
}
interface GhRelease {
  tag_name: string;
  published_at: string;
}

const ghHeaders = (accept: string) => ({
  Accept: accept,
  ...(env.GITHUB_TOKEN ? { Authorization: `Bearer ${env.GITHUB_TOKEN}` } : {}),
});

export function getProjectStats(
  template: Pick<Template, 'description' | 'note' | 'image'>,
  fetch: typeof globalThis.fetch,
): Promise<ProjectStats | null> {
  const repos = candidateRepos(template);
  if (!repos.length) return Promise.resolve(null);

  return cached(`gh:${repos.join(',')}`, DAY, async () => {
    const headers = ghHeaders('application/vnd.github+json');
    for (const repo of repos) {
      const data = await fetchJson<GhRepo>(`https://api.github.com/repos/${repo}`, { headers, fetch });
      if (!data) continue;

      const release = await fetchJson<GhRelease>(`https://api.github.com/repos/${repo}/releases/latest`, { headers, fetch });
      const license = data.license?.spdx_id;
      return {
        repo,
        url: `https://github.com/${repo}`,
        stars: data.stargazers_count,
        forks: data.forks_count,
        license: license && license !== 'NOASSERTION' ? license : null,
        language: data.language,
        updatedAt: data.pushed_at,
        latestRelease: release?.tag_name ?? null,
        releasedAt: release?.published_at ?? null,
        homepage: httpsOnly(data.homepage),
        archived: data.archived,
      };
    }
    return null;
  });
}

// Where a template was sourced from: its listing's maintainer, else wherever its stackfile lives
const SOURCE_REPO = /^https:\/\/github\.com\/([\w.-]+)\/([\w.-]+?)(?:\.git)?\/?$/i;

/* New issue link on the repo this template came from, null if unknown or it doesn't take issues */
export async function getIssuesUrl(
  template: Pick<Template, 'title' | 'maintainer' | 'repository'>,
  fetch: typeof globalThis.fetch,
): Promise<string | null> {
  const match = [template.maintainer, template.repository?.url].map((url) => url?.trim().match(SOURCE_REPO)).find(Boolean);
  if (!match) return null;
  const repo = `${match[1]}/${match[2]}`;
  // '' (not null) for disabled trackers, so the cache keeps that for the day
  const issues = await cached(`gh:issues:${repo.toLowerCase()}`, DAY, async () => {
    const data = await fetchJson<{ html_url: string; has_issues: boolean; archived: boolean }>(
      `https://api.github.com/repos/${repo}`,
      { headers: ghHeaders('application/vnd.github+json'), fetch },
    );
    if (!data) return null;
    return data.has_issues && !data.archived ? `${data.html_url}/issues/new` : '';
  });
  return issues ? `${issues}?title=${encodeURIComponent(`${baseTitle(template.title)} - Deployment is broken`)}` : null;
}

export interface GhReleaseNotes {
  tag_name: string;
  name: string | null;
  body: string | null;
  html_url: string;
}

export function getReleases(repo: string, fetch: typeof globalThis.fetch): Promise<GhReleaseNotes[] | null> {
  return cached(`gh:releases:${repo}`, DAY, () =>
    fetchJson<GhReleaseNotes[]>(`https://api.github.com/repos/${repo}/releases?per_page=30`, {
      headers: ghHeaders('application/vnd.github+json'),
      fetch,
    }),
  );
}

const isAbsolute = (url: string) => /^[a-z][\w+.-]*:|^\/\/|^#/i.test(url);

// Point the README's relative links/images back at the repo, so they don't 404 here
function absolutify(md: string, repo: string): string {
  const raw = `https://raw.githubusercontent.com/${repo}/HEAD/`;
  const blob = `https://github.com/${repo}/blob/HEAD/`;
  const resolve = (base: string, url: string) => {
    try {
      return new URL(url.replace(/^\//, ''), base).href;
    } catch {
      return url;
    }
  };
  return md
    .replace(/(!\[[^\]]*\]\()([^)\s]+)/g, (m, pre, url) => (isAbsolute(url) ? m : pre + resolve(raw, url)))
    .replace(/((?<!!)\[[^\]]*\]\()([^)\s]+)/g, (m, pre, url) => (isAbsolute(url) ? m : pre + resolve(blob, url)))
    .replace(/(<(?:img|source)[^>]*\ssrc=")([^"]+)/gi, (m, pre, url) => (isAbsolute(url) ? m : pre + resolve(raw, url)))
    .replace(/(<a[^>]*\shref=")([^"]+)/gi, (m, pre, url) => (isAbsolute(url) ? m : pre + resolve(blob, url)));
}

export function getReadme(repo: string, fetch: typeof globalThis.fetch): Promise<string | null> {
  return cached(`gh:readme:${repo}`, DAY, async () => {
    const url = `https://api.github.com/repos/${repo}/readme`;
    const md = await fetchText(url, { headers: ghHeaders('application/vnd.github.raw+json'), fetch });
    return md ? absolutify(md, repo) : null;
  });
}
