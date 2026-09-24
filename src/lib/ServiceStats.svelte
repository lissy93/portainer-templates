<script lang="ts">
  import type { TemplateOrService, Volume, Environment, Build } from '$src/Types';

  let { template }: { template: TemplateOrService } = $props();

  type Row = { label: string; values: string[]; href?: string };

  const typeNames: Record<number, string> = { 1: 'Container', 2: 'Swarm', 3: 'Compose', 4: 'Edge stack' };
  const volumeText = (v: Volume) => `${v.container}${v.bind ? ` : ${v.bind}` : ''}`;
  const envText = (e: Environment) =>
    `${e.name}=${e.value ?? e.default ?? e.select?.find((o) => o.default)?.value ?? "''"}`;
  const one = (value?: string | null): string[] => (value ? [value] : []);
  // long form build is an object, so show its context and dockerfile
  const buildText = (b?: Build) =>
    typeof b === 'object' && b ? [b.context || '.', b.dockerfile && `(${b.dockerfile})`].filter(Boolean).join(' ') : b;

  const rows: Row[] = $derived(
    [
      { label: 'Type', values: one(template.type ? typeNames[template.type] ?? 'Unknown' : null) },
      { label: 'Platform', values: one(template.platform) },
      { label: 'Image', values: one(template.image) },
      { label: 'Command', values: one(template.command) },
      { label: 'Entrypoint', values: one(template.entrypoint) },
      { label: 'Interactive', values: typeof template.interactive === 'boolean' ? [template.interactive ? 'Yes' : 'No'] : [] },
      { label: 'Privileged', values: one(template.privileged ? 'Yes' : null) },
      { label: 'Ports', values: template.ports ?? [] },
      { label: 'Volumes', values: (template.volumes ?? []).map(volumeText) },
      { label: 'Env vars', values: (template.env ?? []).map(envText) },
      { label: 'Labels', values: (template.labels ?? []).map((l) => `${l.name}=${l.value}`) },
      { label: 'Restart', values: one(template.restart_policy) },
      { label: 'Build', values: one(buildText(template.build)) },
      { label: 'Source', values: one(template.repository ? 'Repo' : null), href: template.repository?.url },
    ].filter((r) => r.values.length),
  );
</script>

{#if rows.length}
<div class="stats">
  <h3 class="heading">Configuration</h3>
  {#each rows as row (row.label)}
    <span class="lbl">{row.label}</span>
    <div class="val">
      {#if row.href}
        <a href={row.href} target="_blank" rel="noreferrer" title={row.values[0]}>{row.values[0]}</a>
      {:else}
        {#each row.values as value}
          <code title={value}>{value}</code>
        {/each}
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
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: baseline;
    align-content: start;
    gap: 0.35rem 0.85rem;

    .heading {
      grid-column: 1 / -1;
      margin: 0 0 0.25rem;
      font-size: 0.8rem;
      font-weight: 500;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      opacity: 0.6;
    }
    .lbl {
      font-weight: 500;
      white-space: nowrap;
      opacity: 0.75;
    }
    .val {
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
      code,
      a {
        display: block;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
      }
      a { color: var(--accent); }
    }
  }
</style>
