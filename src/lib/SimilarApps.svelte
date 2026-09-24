<script lang="ts">
  import type { SimilarApp } from '$src/Types';
  import Logo from '$lib/Logo.svelte';
  import Collapsible from '$lib/Collapsible.svelte';

  let { items }: { items: SimilarApp[] } = $props();
  let open = $state(true);
</script>

{#if items.length}
<Collapsible title="Similar apps" bind:open>
  <ul class="grid">
    {#each items as app (app.slug)}
      <li>
        <a class="card" href="/{app.slug}" title="Install {app.title} with Portainer">
          <Logo src={app.logo} name="{app.title} logo" />
          <span class="title">{app.title}</span>
          {#if app.category}<span class="cat">{app.category}</span>{/if}
        </a>
      </li>
    {/each}
  </ul>
</Collapsible>
{/if}

<style lang="scss">
  .grid {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 0.75rem;
  }
  .card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.4rem;
    text-align: center;
    padding: 1rem 0.75rem;
    background: var(--card-2);
    border-radius: 6px;
    color: var(--foreground);
    text-decoration: none;
    transition: transform 0.2s ease, background 0.2s ease;
    &:hover {
      transform: translateY(-3px);
      background: var(--background);
    }
    @media (prefers-reduced-motion: reduce) {
      transition: none;
    }
  }
  .title {
    font-weight: 500;
    max-width: 100%;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  .cat {
    font-size: 0.8rem;
    opacity: 0.6;
  }
</style>
