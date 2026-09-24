<script lang="ts">
  import Button from '$lib/Button.svelte';
  import { gitHubRepo } from '$src/constants';

  let { total }: { total?: number } = $props();

  const links = [
    { to: '/usage', icon: 'portainer', label: 'Install on Portainer' },
    { to: gitHubRepo, icon: 'github', label: 'View on GitHub' },
    { to: '/changelog', icon: 'changelog', label: 'Changelog' },
    { to: '/search', icon: 'search', label: 'Search' },
  ];
</script>

<div class="hero">
  <header>
    <h1>Portainer Templates</h1>
    <p class="sub-title">The largest single collection, of ready-to-go Docker apps</p>
  </header>

  <nav>
    {#each links as { to, icon, label } (to)}
      <Button {to} {icon}>{label}</Button>
    {/each}
  </nav>

  {#if total}
    <p class="count">Currently tracking {total.toLocaleString('en-US')} templates</p>
  {/if}
</div>

<style lang="scss">
  .hero {
    padding: 2rem 0;
    text-align: center;
  }

  h1 {
    font-size: clamp(2.5rem, 15vw, 4rem);
    margin: 0 auto;
    background: var(--gradient);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    color: transparent;
  }

  .sub-title {
    margin: 0 auto;
    font-size: 1.4rem;
    font-style: italic;
    font-weight: 200;
  }

  nav {
    display: flex;
    justify-content: center;
    flex-wrap: wrap;
    gap: 0.5rem 1rem;
    margin-top: 1.5rem;
  }

  .count {
    margin: 1rem auto 0;
    font-size: 0.9rem;
    opacity: 0.6;
  }
</style>
