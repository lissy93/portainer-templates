<script lang="ts">
  import type { ProjectStats } from '$src/Types';
  import { formatBigNumber, timeAgo } from '$lib/format';
  import Icon from '$lib/Icon.svelte';

  let { project }: { project: ProjectStats } = $props();

  type Row = { icon: string; label: string; value: string | null; href?: string | null };

  const stats: Row[] = $derived(
    [
      { icon: 'github', label: 'Repo', value: project.repo, href: project.url },
      { icon: 'star', label: 'Stars', value: formatBigNumber(project.stars) },
      { icon: 'fork', label: 'Forks', value: formatBigNumber(project.forks) },
      { icon: 'code', label: 'Language', value: project.language },
      { icon: 'license', label: 'License', value: project.license },
      { icon: 'changelog', label: 'Latest', value: project.latestRelease && (project.releasedAt ? `${project.latestRelease} · ${timeAgo(project.releasedAt)}` : project.latestRelease), href: project.latestRelease && `${project.url}/releases/tag/${project.latestRelease}` },
      { icon: 'updated', label: 'Updated', value: timeAgo(project.updatedAt) },
      { icon: 'link', label: 'Website', value: project.homepage?.replace(/^https?:\/\//, '') ?? null, href: project.homepage },
      { icon: 'status', label: 'Status', value: project.archived ? 'archived' : null },
    ].filter((stat) => !!stat.value),
  );
</script>

{#if stats.length}
<div class="stats">
  <h3 class="heading">Source details</h3>
  {#each stats as stat (stat.label)}
    <div class="row">
      <span class="lbl">
        <Icon name={stat.icon} color="var(--accent)" />
        {stat.label}:
      </span>
      {#if stat.href}
        <a href={stat.href} target="_blank" rel="noreferrer">{stat.value}</a>
      {:else}
        <span>{stat.value}</span>
      {/if}
    </div>
  {/each}
</div>
{/if}

<style lang="scss">
  .stats {
    background: var(--card-2);
    padding: 1rem;
    border-radius: 6px;
    .row {
      display: flex;
      align-items: start;
    }
    .heading {
      margin: 0 0 0.5rem;
      font-size: 0.8rem;
      font-weight: 500;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      opacity: 0.6;
    }
    .lbl {
      font-weight: 500;
      margin-right: 0.5rem;
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      :global(svg) { opacity: 0.7; }
    }
    a {
      color: var(--accent);
      min-width: 0;
    }
  }
</style>
