<script lang="ts">
  import Logo from '$lib/Logo.svelte';
  import Icon from '$lib/Icon.svelte';
  import { formatBigNumber, formatBytes, listingTitle, timeAgo } from '$lib/format';
  import { lastUpdated } from '$lib/search';
  import type { SearchEntry } from '$src/Types';

  let { items }: { items: { entry: SearchEntry; plain: string }[] } = $props();

  const num = (n: number) => (n ? formatBigNumber(n) : '0');

  type Stat = { icon: string; label: string; value: string };
  const rowStats = (e: SearchEntry): Stat[] => {
    const updated = lastUpdated(e);
    return [
      e.pulls != null && { icon: 'download', label: 'Docker Hub downloads', value: num(e.pulls) },
      e.dockerStars != null && { icon: 'star', label: 'Docker Hub stars', value: num(e.dockerStars) },
      e.ghStars != null && { icon: 'github', label: 'GitHub stars', value: num(e.ghStars) },
      !!e.size && { icon: 'stack', label: 'Compressed size', value: formatBytes(e.size) },
      !!updated && { icon: 'updated', label: 'Last updated', value: timeAgo(new Date(updated).toISOString()) },
    ].filter((s): s is Stat => !!s);
  };
</script>

<ol class="results">
  {#each items as { entry, plain } (entry.slug)}
    <li>
      <a class="row" href="/{entry.slug}">
        <Logo src={entry.logo} name={entry.title} />
        <div class="info">
          <h2>{listingTitle(entry.title, entry.primary)}</h2>
          <p class="description">{plain}</p>
          {#if entry.architectures?.length}
            <p class="archs" title="Supported architectures">
              {#each entry.architectures.slice(0, 4) as a (a)}<span>{a}</span>{/each}
              {#if entry.architectures.length > 4}<span>+{entry.architectures.length - 4}</span>{/if}
            </p>
          {/if}
        </div>
        <dl class="stats">
          {#each rowStats(entry) as stat (stat.label)}
            <div class="stat" title={stat.label}>
              <dt class="sr-only">{stat.label}</dt>
              <dd><Icon name={stat.icon} color="var(--accent)" /> {stat.value}</dd>
            </div>
          {/each}
        </dl>
      </a>
    </li>
  {/each}
</ol>

<style lang="scss">
  .results {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;

    .row {
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: 1rem;
      align-items: center;
      background: var(--card);
      border-radius: 6px;
      padding: 0.75rem 1rem;
      color: var(--foreground);
      text-decoration: none;
      transition: all 0.3s ease-in-out;
      &:hover { box-shadow: var(--shadow); }
    }
    .info {
      min-width: 0;
      h2 {
        margin: 0;
        font-size: 1.2rem;
        font-weight: 600;
      }
      .description {
        margin: 0;
        font-style: italic;
        font-weight: 200;
        overflow: hidden;
        word-break: break-word;
        display: -webkit-box;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
        line-clamp: 2;
      }
      .archs {
        margin: 0.35rem 0 0;
        display: flex;
        flex-wrap: wrap;
        gap: 0.3rem;
        span {
          background: var(--card-2);
          border-radius: 4px;
          padding: 0 0.35rem;
          font-size: 0.7rem;
          opacity: 0.8;
        }
      }
    }
    .stats {
      margin: 0;
      display: grid;
      grid-template-columns: repeat(3, auto);
      gap: 0.3rem 1rem;
      justify-items: start;
      .stat dd {
        margin: 0;
        display: flex;
        align-items: center;
        gap: 0.4rem;
        font-size: 0.9rem;
        white-space: nowrap;
        :global(svg) { opacity: 0.8; }
      }
    }
  }

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    margin: -1px;
    padding: 0;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
    border: 0;
  }

  @media (max-width: 768px) {
    .results .row {
      grid-template-columns: auto 1fr;
      .stats {
        grid-column: 1 / -1;
        grid-template-columns: repeat(auto-fit, minmax(5.5rem, max-content));
        width: 100%;
      }
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .results .row { transition: none; }
  }
</style>
