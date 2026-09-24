<script lang="ts">
  import Icon from '$lib/Icon.svelte';
  import { inlineMarkdown } from '$lib/format';
  import type { TemplateStatus } from '$src/Types';

  let { status }: { status: TemplateStatus } = $props();
</script>

<aside class="status-banner">
  <Icon name="warning" color="var(--red)" width="20px" height="20px" />
  <div>
    <strong>This template is currently marked as {status.status}</strong>
    {#if status.note}<p>{@html inlineMarkdown(status.note)}</p>{/if}
  </div>
</aside>

<style lang="scss">
  .status-banner {
    display: flex;
    gap: 0.75rem;
    align-items: flex-start;
    max-width: 1000px;
    margin: 1rem auto;
    padding: 0.75rem 1rem;
    border-radius: 6px;
    border: 1px solid color-mix(in srgb, var(--red) 50%, transparent);
    background: color-mix(in srgb, var(--red) 12%, var(--card));
    overflow-wrap: break-word;
    > :global(svg) {
      flex-shrink: 0;
      margin-top: 0.15rem;
    }
    div {
      min-width: 0;
    }
    strong {
      font-weight: 500;
    }
    p {
      margin: 0.25rem 0 0;
      opacity: 0.85;
    }
    :global(code) {
      background: var(--background);
      padding: 0.1em 0.4em;
      border-radius: 4px;
    }
  }
</style>
