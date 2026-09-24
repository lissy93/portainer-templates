<script lang="ts">
  import type { TemplateCard } from '$src/Types';
  import Logo from '$lib/Logo.svelte';
  import Icon from '$lib/Icon.svelte';
  import { slugify, parseDescription, listingTitle } from '$lib/format';

  let { templates }: { templates: TemplateCard[] } = $props();
</script>

<section class="templates">
  {#each templates as template (template.title)}
    {@const descHtml = parseDescription(template.description)}
    <a class="template-card" href="/{slugify(template.title)}">
      <h3>
        {listingTitle(template.title, template.primary)}
        {#if template.status}
          <span class="status" role="img" aria-label="Currently {template.status}" title="Currently {template.status}">
            <Icon name="warning" color="var(--red)" />
          </span>
        {/if}
      </h3>
      <div class="template-summary">
        <div class="left">
          <Logo src={template.logo} name={listingTitle(template.title, template.primary)} />
        </div>
        <div class="txt">
          <p class="description" title={template.description}>{#if descHtml}{@html descHtml}{:else}{template.description}{/if}</p>
        </div>
      </div>
    </a>
  {/each}
</section>

<style lang="scss">
section.templates {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(300px, 100%), 1fr));
  gap: 1rem;
  margin: 1rem auto;
  padding: 0 1rem;
  max-width: var(--max-width);
  .template-card {
    padding: 1rem;
    border-radius: 6px;
    background: var(--card);
    display: flex;
    flex-direction: column;
    gap: 1rem;
    transition:all 0.3s ease-in-out;
    text-decoration: none;
    color: var(--foreground);
    &:hover {
      box-shadow: var(--shadow);
    }
    .template-summary {
      display: flex;
      gap: 1rem;
      align-items: start;
    }
    p, h3 {
      margin: 0;
    }
    h3 {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 0.5rem;
    }
    .status {
      display: flex;
      flex-shrink: 0;
    }
    .description {
      font-style: italic;
      font-weight: 200;
      overflow: hidden;
      word-break: break-word;
      text-overflow: ellipsis;
      display: -webkit-box;
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 5;
      line-clamp: 5;
    }
  }
}
</style>
