import { error } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { loadTemplates } from '$lib/server/templates';
import { slugify } from '$lib/format';
import type { ChangelogEntry, ChangelogChanges, ChangeItem, Template } from '$src/Types';
import type { PageServerLoad } from './$types';

const repo = 'lissy93/portainer-templates';
const changelogUrl = `https://raw.githubusercontent.com/${repo}/refs/heads/main/.github/changelog.json`;

interface GhTag { name: string; commit: { sha: string }; }
interface GhRelease { tag_name: string; name: string | null; body: string | null; published_at: string; }
interface GhCommit { commit: { committer: { date: string } }; }
interface RawChange { version: string; added: string[]; removed: string[]; renamed?: { from: string; to: string }[]; updated: { title: string; fields: string[] }[]; }

// patch number of 0 means it's a minor or major release, so we show its notes
const isMinorOrMajor = (version: string) => Number(version.replace(/^v/, '').split('.')[2]) === 0;

/* Shape a raw changelog record into linkable items, dropping tags with nothing to show */
const toChanges = (raw: RawChange | undefined, linkFor: (title: string) => string | null): ChangelogChanges | null => {
  if (!raw) return null;
  const item = (name: string, link: boolean, fields?: string[]): ChangeItem =>
    ({ name, slug: link ? linkFor(name) : null, ...(fields?.length ? { fields } : {}) });
  const changes = {
    added: raw.added.map((n) => item(n, true)),
    updated: raw.updated.map((u) => item(u.title, true, u.fields)),
    renamed: (raw.renamed ?? []).map((r) => ({ ...item(r.to, true), from: r.from })),
    removed: raw.removed.map((n) => item(n, false)),
  };
  return Object.values(changes).some((group) => group.length) ? changes : null;
};

export const load: PageServerLoad = async ({ fetch, setHeaders }) => {
  const token = env.GITHUB_TOKEN;
  const headers: Record<string, string> = {
    Accept: 'application/vnd.github+json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const gh = <T>(path: string): Promise<T> =>
    fetch(`https://api.github.com/repos/${repo}${path}`, { headers }).then((res) => {
      if (!res.ok) throw new Error(`GitHub responded ${res.status}`);
      return res.json() as Promise<T>;
    });

  try {
    const [tags, releases, templates, changelog] = await Promise.all([
      gh<GhTag[]>('/tags?per_page=100'),
      gh<GhRelease[]>('/releases?per_page=100'),
      loadTemplates(fetch).catch(() => [] as Template[]),
      fetch(changelogUrl).then((res) => (res.ok ? res.json() : { entries: [] })).catch(() => ({ entries: [] })) as Promise<{ entries: RawChange[] }>,
    ]);

    const releaseByTag = new Map(releases.map((r) => [r.tag_name, r]));
    const changeByTag = new Map(changelog.entries.map((c) => [c.version, c]));

    // Only link a change to its page when that template still exists on the site
    const liveSlugs = new Set(templates.map((t) => slugify(t.title)));
    const linkFor = (title: string) => (liveSlugs.has(slugify(title)) ? slugify(title) : null);

    const entries: ChangelogEntry[] = await Promise.all(
      tags.map(async (tag) => {
        const release = releaseByTag.get(tag.name);
        // Releases have a publish date, plain tags fall back to their commit date
        const date = release?.published_at
          ?? (await gh<GhCommit>(`/commits/${tag.commit.sha}`)).commit.committer.date;
        return {
          version: tag.name,
          date,
          isRelease: isMinorOrMajor(tag.name),
          title: release?.name ?? null,
          notes: release?.body?.trim() || null,
          changes: toChanges(changeByTag.get(tag.name), linkFor),
        };
      })
    );

    entries.sort((a, b) => b.date.localeCompare(a.date));

    setHeaders({ 'cache-control': 'public, max-age=600, s-maxage=3600, stale-while-revalidate=86400' });
    return { entries };
  } catch {
    throw error(503, 'Could not load the changelog from GitHub. Please try again shortly.');
  }
};
