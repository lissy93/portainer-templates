<script lang="ts">
  import { browser } from '$app/environment';
  import { page, navigating } from '$app/state';
  import { tick, type Snippet } from 'svelte';
  import Header from '$lib/Header.svelte';
  import Footer from '$lib/Footer.svelte';
  import { baseUrl } from '$src/constants';

  let { children }: { children: Snippet } = $props();

  let bottom = $state(false);

  const scrollVisible = (): boolean => {
    return browser ?
      document.documentElement.clientHeight >= document.documentElement.scrollHeight
      : false;
  };

  const isHome = $derived(['/', '/index'].includes(page.url.pathname));

  async function updateFooter() {
    await tick();
    bottom = scrollVisible();
  }

  $effect(() => {
    // Re-check whether the footer should be pinned whenever the route changes
    void navigating.to;
    void page.url.pathname;
    updateFooter();
  });
</script>

<!-- Site-wide tags; page-specific title/description/canonical live in each page's <svelte:head> -->
<svelte:head>
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Portainer Templates" />
  <meta name="theme-color" content="#0ba5ec" />
  <link rel="alternate" type="application/atom+xml" title="Portainer Templates Changelog" href="{baseUrl}/changelog.xml" />
</svelte:head>

<Header floating={isHome} />
<main>
  {@render children()}
</main>
<Footer {bottom} />


<style lang="scss">
  :global(body) {
    --background: #101828;
    --foreground: #ffffff;
    --accent: #0ba5ec;
    --card: #1d2939;
    --card-2: #192432;
    --red: #e5534b;
    --green: #3fb950;
    --blue: #0ba5ec;
    --yellow: #d29922;
    --shadow: 1px 1px 3px 3px #0B9AEC8F;
    --gradient: linear-gradient(to right,#0B9AEC 0%,#6EDFDE 100%);
    --max-width: 1800px;
    margin: 0;
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    font-family: 'Kanit', sans-serif;
    color: var(--foreground);
    background: var(--background);
  }
  :global(::selection) {
    background: var(--accent);
    color: var(--background);
  }
  main {
    padding: 2rem;
    flex: 1;
  }

</style>