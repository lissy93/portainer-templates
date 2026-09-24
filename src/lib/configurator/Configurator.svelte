<script lang="ts">
  import Icon from '$lib/Icon.svelte';
  import AppPicker from './AppPicker.svelte';
  import AppCard from './AppCard.svelte';
  import MethodConfigurator from './MethodConfigurator.svelte';
  import { availableMethods } from './config';
  import type { AppOption, ConfigureResponse } from './config';

  let apps = $state<AppOption[]>([]);
  let appsLoading = $state(false);
  let selected = $state<AppOption | null>(null);
  let data = $state<ConfigureResponse | null>(null);
  let version = $state('latest');
  let configLoading = $state(false);
  let loadError = $state('');
  let refocusPicker = $state(false);
  let request = 0;

  const reset = () => {
    request++;
    selected = null;
    data = null;
    loadError = '';
    configLoading = false;
    refocusPicker = true;
  };

  const loadApps = async () => {
    if (apps.length || appsLoading) return;
    appsLoading = true;
    try {
      const res = await fetch('/api/apps.json');
      if (res.ok) apps = await res.json();
    } finally {
      appsLoading = false;
    }
  };

  const select = async (app: AppOption) => {
    const token = ++request;
    selected = app;
    configLoading = true;
    loadError = '';
    data = null;
    try {
      const res = await fetch(`/api/configure/${app.slug}.json`);
      if (!res.ok) throw new Error(String(res.status));
      const payload: ConfigureResponse = await res.json();
      if (token !== request) return;
      data = payload;
      version = 'latest';
    } catch {
      if (token === request) loadError = `Couldn't load the template for ${app.title}. Try again in a moment.`;
    } finally {
      if (token === request) configLoading = false;
    }
  };

  const available = $derived(data ? availableMethods(data) : []);

  const versionInfo = $derived.by(() => {
    if (!data?.meta) return null;
    const picked = data.meta.versions.find((v) => v.name === version);
    return picked ?? { size: data.meta.size ?? 0, platforms: data.meta.architectures, date: '' };
  });
</script>

<section class="configurator">
  <h2>Install without Portainer</h2>
  <p class="intro">
    Install a single app, without needing Portainer. Select an app, select an install method, and fill in the fields to get a complete run/config command.
  </p>

  {#if data}
    <div class="selected-app">
      <button type="button" class="start-over" onclick={reset} title="Reset and choose a different app">
        <Icon name="updated" width="12px" height="12px" /> Start over
      </button>
      <AppCard
        template={data.template}
        architectures={versionInfo?.platforms ?? []}
        size={versionInfo?.size ?? null}
        pulls={data.stats?.pulls ?? null}
        updated={data.stats?.updated || versionInfo?.date || ''}
        github={data.github}
      />
    </div>
  {:else}
    <div class="panel picker-panel">
      <AppPicker {apps} loading={appsLoading} onopen={loadApps} onselect={select} focusOnMount={refocusPicker} />
    </div>
  {/if}

  {#if configLoading}
    <p class="status" aria-live="polite">Loading {selected?.title}&hellip;</p>
  {:else if loadError}
    <p class="status error" role="alert">{loadError}</p>
  {:else if data}
    {#if available.length}
      {#key data}
        <MethodConfigurator {data} bind:version />
      {/key}
    {:else}
      <p class="status">
        {data.template.title} can't be configured here, as its template doesn't define a runnable image.
        See the <a href="/{selected?.slug}">app page</a> for install options.
      </p>
    {/if}
  {/if}
</section>

<style lang="scss">
  .configurator {
    background: var(--card);
    padding: 1rem;
    border-radius: 6px;
    margin: 1rem auto 4rem auto;
    max-width: 1000px;
    h2 {
      margin: 0 0 0.5rem;
      font-size: 2rem;
    }
    .intro {
      margin: 0 0 1rem;
      font-size: 1.1rem;
      opacity: 0.5;
      font-style: italic;
    }
    .status {
      margin: 1rem 0 0;
      opacity: 0.8;
      &.error {
        color: #e5534b;
        opacity: 1;
      }
      a {
        color: var(--accent);
      }
    }
    .panel {
      margin: 1rem 0 0;
      padding: 0.75rem;
      border: none;
      border-radius: 6px;
      background: var(--card-2);
    }
    .selected-app {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      margin: 1rem 0 0;
    }
    .start-over {
      align-self: flex-start;
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
      padding: 0.2rem 0.5rem;
      background: var(--card-2);
      border: none;
      border-radius: 6px;
      color: var(--foreground);
      font: inherit;
      font-size: 0.75rem;
      cursor: pointer;
      transition: all 0.2s ease-in-out;
      &:hover {
        color: var(--accent);
      }
      &:focus-visible {
        outline: 2px solid var(--accent);
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .start-over {
        transition: none;
      }
    }
  }
</style>
