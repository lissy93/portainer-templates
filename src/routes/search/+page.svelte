<script lang="ts">
  import { browser } from '$app/environment';
  import { replaceState } from '$app/navigation';
  import { page } from '$app/state';
  import Meta from '$lib/Meta.svelte';
  import NoResults from '$lib/NoResults.svelte';
  import SearchResults from '$lib/SearchResults.svelte';
  import { isHiddenVariant, timeAgo } from '$lib/format';
  import { buildDoc, lastUpdated, rankDoc, tokenize } from '$lib/search';
  import { baseUrl } from '$src/constants';
  import type { SearchEntry } from '$src/Types';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  const PER_PAGE = 25;
  const DAY = 86_400_000;

  const description = 'Advanced search across 600+ self-hosted apps and stacks. Sort by Docker Hub downloads, stars or image size, and filter by category, platform, architecture and more.';

  const jsonLd = JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: 'App Search - Portainer Templates',
    url: `${baseUrl}/search`,
    description,
  }).replace(/</g, '\\u003c');

  type SortId = 'match' | 'pulls' | 'dockerStars' | 'ghStars' | 'updated' | 'newest' | 'size' | 'title';
  const sorts: Record<SortId, { label: string; value: (e: SearchEntry) => number | string | undefined; dir: 1 | -1 }> = {
    match: { label: 'Best match', value: (e) => e.pulls, dir: -1 },
    pulls: { label: 'Most downloads', value: (e) => e.pulls, dir: -1 },
    dockerStars: { label: 'Docker Hub stars', value: (e) => e.dockerStars, dir: -1 },
    ghStars: { label: 'GitHub stars', value: (e) => e.ghStars, dir: -1 },
    updated: { label: 'Recently updated', value: lastUpdated, dir: -1 },
    newest: { label: 'Newest on Docker Hub', value: (e) => Date.parse(e.imageCreated ?? '') || undefined, dir: -1 },
    size: { label: 'Smallest image', value: (e) => e.size, dir: 1 },
    title: { label: 'Name (A to Z)', value: (e) => e.title.toLowerCase(), dir: 1 },
  };

  // options with more than a few matches, most common first
  const countValues = (get: (e: SearchEntry) => string[] | undefined): string[] => {
    const counts = new Map<string, number>();
    for (const e of data.entries) for (const v of get(e) ?? []) counts.set(v, (counts.get(v) ?? 0) + 1);
    return [...counts].filter(([, n]) => n > 3).sort((a, b) => b[1] - a[1]).map(([v]) => v);
  };
  const categoryOptions = $derived(countValues((e) => e.categories?.map((c) => c.toLowerCase())));
  const archOptions = $derived(countValues((e) => e.architectures));
  const platformOptions = $derived([...new Set(data.entries.map((e) => e.platform).filter((p): p is string => !!p))]);

  const params = browser ? page.url.searchParams : new URLSearchParams();
  const param = (key: string) => params.get(key) ?? '';

  let q = $state(param('q') || param('search'));
  let sort = $state<SortId>(param('sort') in sorts ? (param('sort') as SortId) : 'match');
  let category = $state(param('category'));
  let platform = $state(param('platform'));
  let kind = $state(param('type'));
  let arch = $state(param('arch'));
  let updatedDays = $state(param('updated'));
  let maxSize = $state(param('size'));
  let pageNum = $state(Math.max(1, Number(param('page')) || 1));

  const docs = $derived(data.entries.map(buildDoc));

  const tokens = $derived(tokenize(q));
  const matches = $derived(
    docs
      .map((d) => ({ ...d, rank: tokens.length ? rankDoc(d, tokens) : 0 }))
      .filter(({ entry, rank }) => {
        if (tokens.length && !rank) return false;
        // one result per app, unless filtering by type where each variant stands alone
        if (!kind && isHiddenVariant(entry.slug, entry.primary)) return false;
        if (category && !(entry.categories ?? []).some((c) => c.toLowerCase() === category)) return false;
        if (platform && entry.platform !== platform) return false;
        if (kind && (kind === 'container') !== (entry.type === 1)) return false;
        if (arch && !(entry.architectures ?? []).includes(arch)) return false;
        if (updatedDays && Date.now() - (lastUpdated(entry) ?? 0) > Number(updatedDays) * DAY) return false;
        if (maxSize && !(entry.size && entry.size <= Number(maxSize) * 1_048_576)) return false;
        return true;
      }),
  );

  const sorted = $derived.by(() => {
    const { value, dir } = sorts[sort];
    return [...matches].sort((a, b) => {
      if (sort === 'match' && a.rank !== b.rank) return b.rank - a.rank;
      const av = value(a.entry);
      const bv = value(b.entry);
      if (av == null || bv == null) return (av == null ? 1 : 0) - (bv == null ? 1 : 0) || a.entry.title.localeCompare(b.entry.title);
      const cmp = typeof av === 'string' && typeof bv === 'string' ? av.localeCompare(bv) : Number(av) - Number(bv);
      return cmp * dir || a.entry.title.localeCompare(b.entry.title);
    });
  });

  const totalPages = $derived(Math.max(1, Math.ceil(sorted.length / PER_PAGE)));
  const current = $derived(Math.min(pageNum, totalPages));
  const results = $derived(sorted.slice((current - 1) * PER_PAGE, current * PER_PAGE));

  const pageList = $derived.by(() => {
    const pages: (number | null)[] = [];
    for (let p = 1; p <= totalPages; p++) {
      if (p === 1 || p === totalPages || Math.abs(p - current) <= 1) pages.push(p);
      else if (pages[pages.length - 1] !== null) pages.push(null);
    }
    return pages;
  });

  const resetPage = () => (pageNum = 1);

  const clearAll = () => {
    q = '';
    sort = 'match';
    category = platform = kind = arch = updatedDays = maxSize = '';
    pageNum = 1;
  };

  const goPage = (p: number) => {
    pageNum = Math.min(Math.max(1, p), totalPages);
    window.scrollTo(0, 0);
  };

  // keep filters shareable via the URL, without polluting history
  $effect(() => {
    const p = new URLSearchParams();
    if (q.trim()) p.set('q', q.trim());
    if (sort !== 'match') p.set('sort', sort);
    if (category) p.set('category', category);
    if (platform) p.set('platform', platform);
    if (kind) p.set('type', kind);
    if (arch) p.set('arch', arch);
    if (updatedDays) p.set('updated', updatedDays);
    if (maxSize) p.set('size', maxSize);
    if (current > 1) p.set('page', String(current));
    const qs = p.toString();
    try {
      replaceState(qs ? `?${qs}` : '/search', {});
    } catch {
      // router not ready on first run, no harm done
    }
  });
</script>

<Meta title="App Search | Portainer Templates" {description} path="/search" />

<svelte:head>
  {@html '<script type="application/ld+json">' + jsonLd + '</scr' + 'ipt>'}
</svelte:head>

<section class="search-page">
  <h1>App Search</h1>
  <p class="intro">Advanced search: find Portainer templates for over 500 self-hosted Docker apps</p>

  <form class="controls" onsubmit={(e) => e.preventDefault()}>
    <div class="primary">
      <label class="field grow">
        <span>Search</span>
        <input type="search" placeholder="App name, description or category..." bind:value={q} oninput={resetPage} />
      </label>
      <label class="field">
        <span>Sort by</span>
        <select bind:value={sort} onchange={resetPage}>
          {#each Object.entries(sorts) as [id, s] (id)}
            <option value={id}>{s.label}</option>
          {/each}
        </select>
      </label>
    </div>
    <div class="secondary">
      <label class="field">
        <span>Category</span>
        <select bind:value={category} onchange={resetPage}>
          <option value="">All</option>
          {#each categoryOptions as cat (cat)}
            <option value={cat}>{cat}</option>
          {/each}
        </select>
      </label>
      <label class="field">
        <span>Platform</span>
        <select bind:value={platform} onchange={resetPage}>
          <option value="">All</option>
          {#each platformOptions as p (p)}
            <option value={p}>{p}</option>
          {/each}
        </select>
      </label>
      <label class="field">
        <span>Type</span>
        <select bind:value={kind} onchange={resetPage}>
          <option value="">All</option>
          <option value="container">Container</option>
          <option value="stack">Stack</option>
        </select>
      </label>
      <label class="field">
        <span>Architecture</span>
        <select bind:value={arch} onchange={resetPage}>
          <option value="">All</option>
          {#each archOptions as a (a)}
            <option value={a}>{a}</option>
          {/each}
        </select>
      </label>
      <label class="field">
        <span>Updated within</span>
        <select bind:value={updatedDays} onchange={resetPage}>
          <option value="">Any time</option>
          <option value="7">A week</option>
          <option value="30">A month</option>
          <option value="183">6 months</option>
          <option value="365">A year</option>
        </select>
      </label>
      <label class="field">
        <span>Image size</span>
        <select bind:value={maxSize} onchange={resetPage}>
          <option value="">Any</option>
          <option value="50">Under 50 MB</option>
          <option value="100">Under 100 MB</option>
          <option value="250">Under 250 MB</option>
          <option value="500">Under 500 MB</option>
          <option value="1024">Under 1 GB</option>
        </select>
      </label>
      <button type="button" class="clear" onclick={clearAll}>Clear filters</button>
    </div>
  </form>

  <p class="summary" aria-live="polite">
    {sorted.length} of {data.entries.length} templates
    {#if totalPages > 1}&middot; page {current} of {totalPages}{/if}
    &middot; stats refreshed {timeAgo(data.generated)}
  </p>

  {#if results.length}
    <SearchResults items={results} />
  {:else}
    <NoResults />
  {/if}

  {#if totalPages > 1}
    <nav class="pagination" aria-label="Search result pages">
      <button disabled={current === 1} onclick={() => goPage(current - 1)}>Prev</button>
      {#each pageList as p, i (p ?? `gap-${i}`)}
        {#if p === null}
          <span class="gap" aria-hidden="true">&hellip;</span>
        {:else}
          <button class:active={p === current} aria-current={p === current ? 'page' : undefined} onclick={() => goPage(p)}>{p}</button>
        {/if}
      {/each}
      <button disabled={current === totalPages} onclick={() => goPage(current + 1)}>Next</button>
    </nav>
  {/if}
</section>

<style lang="scss">
  .search-page {
    max-width: 75rem;
    margin: 0 auto;

    h1 {
      margin: 0;
      font-size: 2.5rem;
    }
    .intro {
      margin: 0 0 1.5rem;
      font-weight: 200;
      font-style: italic;
      opacity: 0.8;
    }
  }

  .controls {
    background: var(--card);
    border-radius: 6px;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;

    .primary, .secondary {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      align-items: end;
    }
    .field {
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
      &.grow { flex: 1 1 16rem; }
      span {
        font-size: 0.7rem;
        font-weight: 500;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        opacity: 0.6;
      }
    }
    input, select {
      background: var(--card-2);
      border: 1px solid transparent;
      color: var(--foreground);
      font-family: inherit;
      font-size: 0.95rem;
      padding: 0.5rem 0.75rem;
      border-radius: 6px;
      transition: all 0.3s ease-in-out;
      &:focus, &:hover {
        box-shadow: var(--shadow);
        outline: none;
      }
    }
    select { text-transform: capitalize; }
    .clear {
      background: var(--card-2);
      border: 1px solid transparent;
      color: var(--foreground);
      font-family: inherit;
      font-size: 0.9rem;
      padding: 0.5rem 0.75rem;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.3s ease-in-out;
      &:hover { background: var(--gradient); }
    }
  }

  .summary {
    margin: 1rem 0 0.5rem;
    font-size: 0.9rem;
    opacity: 0.7;
  }

  .pagination {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    justify-content: center;
    margin: 1.5rem 0;
    button {
      background: var(--card);
      border: 1px solid transparent;
      color: var(--foreground);
      font-family: inherit;
      font-size: 0.9rem;
      padding: 0.35rem 0.7rem;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.3s ease-in-out;
      &:hover:not(:disabled) { background: var(--gradient); }
      &:disabled { opacity: 0.4; cursor: default; }
      &.active { background: var(--accent); color: var(--background); }
    }
    .gap { align-self: center; opacity: 0.5; }
  }

  @media (max-width: 768px) {
    .search-page h1 { font-size: 2rem; }
  }

  @media (prefers-reduced-motion: reduce) {
    .controls input, .controls select, .controls .clear,
    .pagination button { transition: none; }
  }
</style>
