<script lang="ts">
  import snarkdown from 'snarkdown';
  import { slide } from 'svelte/transition';
  import { prefersReducedMotion } from 'svelte/motion';
  import CopyLink from '$lib/CopyLink.svelte';
  import Icon from '$lib/Icon.svelte';
  import { gitHubRepo } from '$src/constants';
  import type { ChangelogEntry } from '$src/Types';

  let { entry }: { entry: ChangelogEntry } = $props();

  const templatesUrl = $derived(
    `https://raw.githubusercontent.com/lissy93/portainer-templates/refs/tags/${entry.version}/templates.json`
  );

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });

  const href = $derived(
    entry.title || entry.notes
      ? `${gitHubRepo}/releases/tag/${entry.version}`
      : `${gitHubRepo}/tree/${entry.version}`
  );

  const showNotes = $derived(entry.isRelease && !!entry.notes);

  // release notes start clipped, sliding open to their measured height
  const COLLAPSED_PX = 64;
  const uid = $props.id();
  let expanded = $state(false);
  let fullHeight = $state(0);
  // assume long until measured, and skip the toggle for just a line of overflow
  const overflows = $derived(!fullHeight || fullHeight > COLLAPSED_PX + 24);
  const maxHeight = $derived(overflows && !expanded ? COLLAPSED_PX : fullHeight);

  /* Non-empty change groups for this tag, in a sensible reading order */
  const groups = $derived(
    entry.changes
      ? ([
          { key: 'added', label: 'Added', icon: 'added', items: entry.changes.added },
          { key: 'updated', label: 'Updated', icon: 'updated', items: entry.changes.updated },
          { key: 'renamed', label: 'Renamed', icon: 'renamed', items: entry.changes.renamed },
          { key: 'removed', label: 'Removed', icon: 'removed', items: entry.changes.removed },
        ] as const).filter((group) => group.items.length)
      : []
  );

  // long change lists show a preview, until expanded
  const LIST_MAX = 12;
  const LIST_PREVIEW = 10;
  let showAll = $state<Record<string, boolean>>({});
</script>

{#snippet toggle(open: boolean, controls: string, more: string, onclick: () => void)}
  <button type="button" class="toggle" aria-expanded={open} aria-controls={controls} {onclick}>
    {open ? 'Show less' : more}
    <span class="chevron" aria-hidden="true"></span>
  </button>
{/snippet}

<li class="entry" class:release={entry.isRelease}>
  <span class="marker" aria-hidden="true"></span>
  <div class="meta">
    <h3 class="version-heading">
      <a class="version" {href} target="_blank" rel="noreferrer">{entry.version}</a>
    </h3>
    <time datetime={entry.date}>{formatDate(entry.date)}</time>
    <span class="copy"><CopyLink label="Get {entry.version} templates" url={templatesUrl} /></span>
  </div>

  {#if showNotes}
    <div class="notes">
      {#if entry.title && entry.title !== entry.version}
        <h2>{entry.title}</h2>
      {/if}
      <div id="{uid}-notes" class="clip" class:faded={overflows && !expanded} style:max-height="{maxHeight}px">
        <div class="markdown" bind:offsetHeight={fullHeight}>{@html snarkdown(entry.notes ?? '')}</div>
      </div>
      {#if overflows}
        {@render toggle(expanded, `${uid}-notes`, 'Show more', () => (expanded = !expanded))}
      {/if}
    </div>
  {:else if groups.length}
    <div class="changes">
      {#each groups as group (group.key)}
        {@const long = group.items.length > LIST_MAX}
        {@const items = long && !showAll[group.key] ? group.items.slice(0, LIST_PREVIEW) : group.items}
        <section class="group" data-kind={group.key}>
          <h4>
            <Icon name={group.icon} width="14px" height="14px" />
            {group.label}
            {#if group.items.length > 1}
              <span class="count">{group.items.length}</span>
            {/if}
          </h4>
          <ul id="{uid}-{group.key}">
            {#each items as item (item.name)}
              <li transition:slide={{ duration: prefersReducedMotion.current ? 0 : 250 }}>
                {#if item.slug}
                  <a href="/{item.slug}">{item.name}</a>
                {:else}
                  <span class="name">{item.name}</span>
                {/if}
                {#if item.from}<span class="chip">was {item.from}</span>{/if}
                {#if item.fields?.length}
                  <span class="fields">
                    {#each item.fields as field (field)}<span class="chip">{field}</span>{/each}
                  </span>
                {/if}
              </li>
            {/each}
          </ul>
          {#if long}
            {@render toggle(!!showAll[group.key], `${uid}-${group.key}`, `Show ${group.items.length - LIST_PREVIEW} more`, () => (showAll[group.key] = !showAll[group.key]))}
          {/if}
        </section>
      {/each}
    </div>
  {:else if entry.isRelease}
    <div class="notes"><p class="empty">No release notes provided.</p></div>
  {/if}
</li>

<style lang="scss">
  .entry {
    position: relative;
    padding: 0 0 1.25rem 2rem;
    &:last-child { padding-bottom: 0; }
  }
  .marker {
    position: absolute;
    left: 0;
    top: 4px;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    box-sizing: border-box;
    background: var(--card-2);
    border: 2px solid var(--accent);
  }
  .release .marker {
    background: var(--accent);
    box-shadow: 0 0 0 4px rgba(11, 165, 236, 0.15);
  }
  .meta {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
    .copy {
      margin-left: auto;
      opacity: 0.5;
      transition: opacity 0.05s ease-in-out;
      &:hover, &:focus-within { opacity: 1; }
    }
    .version-heading {
      margin: 0;
      font-size: inherit;
      font-weight: inherit;
      line-height: inherit;
    }
    .version {
      font-size: 1.25rem;
      font-weight: 600;
      color: var(--foreground);
      text-decoration: none;
      &:hover { color: var(--accent); }
    }
    time {
      font-size: 0.9rem;
      opacity: 0.6;
    }
  }
  .entry:not(.release) .version {
    font-size: 1rem;
  }
  .notes {
    margin-top: 0.75rem;
    background: var(--card);
    border-radius: 6px;
    padding: 1rem 1.25rem;
    h2 {
      font-size: 1.5rem;
      margin: 0 0 0.5rem;
    }
    .empty {
      margin: 0;
      opacity: 0.6;
      font-style: italic;
    }
  }
  .clip {
    overflow: hidden;
    transition: max-height 0.35s ease;
    &.faded {
      mask-image: linear-gradient(to bottom, #000 40%, transparent);
    }
  }
  .toggle {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.5rem;
    padding: 0;
    background: none;
    border: none;
    color: var(--accent);
    font: inherit;
    font-size: 0.9rem;
    cursor: pointer;
    .chevron {
      width: 0.45rem;
      height: 0.45rem;
      border-right: 2px solid currentColor;
      border-bottom: 2px solid currentColor;
      transform: translateY(-2px) rotate(45deg);
      transition: transform 0.25s ease;
    }
    &[aria-expanded='true'] .chevron {
      transform: translateY(2px) rotate(-135deg);
    }
    &:hover { text-decoration: underline; }
  }
  @media (prefers-reduced-motion: reduce) {
    .clip, .toggle .chevron { transition: none; }
  }
  .markdown {
    display: flow-root;
    :global(h1), :global(h2), :global(h3) {
      font-size: 1.2rem;
      margin: 1rem 0 0.5rem;
    }
    :global(ul) {
      margin: 0;
      padding-left: 1.25rem;
    }
    :global(a) {
      color: var(--accent);
      text-decoration: none;
    }
    :global(img) { max-width: 100%; }
    :global(pre) {
      background: var(--card-2);
      padding: 1rem;
      border-radius: 6px;
      overflow: auto;
    }
    :global(code) {
      background: var(--card-2);
      padding: 0.1rem 0.3rem;
      border-radius: 4px;
    }
  }
  .changes {
    margin-top: 0.75rem;
    background: var(--card);
    border-radius: 6px;
    padding: 0.85rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .group {
    &[data-kind='added'] { --kind: var(--green); }
    &[data-kind='updated'] { --kind: var(--blue); }
    &[data-kind='renamed'] { --kind: var(--yellow); }
    &[data-kind='removed'] { --kind: var(--red); }
    h4 {
      display: flex;
      align-items: center;
      gap: 0.4rem;
      margin: 0 0 0.4rem;
      font-size: 0.8rem;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--kind);
    }
    .count {
      font-size: 0.7rem;
      font-weight: 400;
      color: var(--foreground);
      opacity: 0.6;
    }
    ul {
      list-style: none;
      margin: 0;
      padding: 0;
      display: flex;
      flex-direction: column;
    }
    li {
      display: flex;
      align-items: baseline;
      flex-wrap: wrap;
      gap: 0.2rem;
      font-size: 0.95rem;
    }
    a {
      color: var(--foreground);
      text-decoration: none;
      border-bottom: 1px solid transparent;
      transition: color 0.1s ease-in-out;
      &:hover, &:focus-visible {
        color: var(--accent);
        border-bottom-color: currentColor;
      }
    }
    &[data-kind='removed'] .name {
      text-decoration: line-through;
      opacity: 0.65;
    }
    .fields {
      display: inline-flex;
      flex-wrap: wrap;
      gap: 0.1rem;
    }
    .chip {
      font-size: 0.65rem;
      padding: 0.05rem 0.35rem;
      border-radius: 4px;
      background: var(--card-2);
      color: var(--foreground);
      opacity: 0.7;
    }
  }
</style>
