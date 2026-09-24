<script lang="ts">
  import { page } from '$app/state'

  import Hero from '$lib/Hero.svelte';
  import ListFilter from '$lib/ListFilter.svelte';
  import Categories from '$lib/Categories.svelte';
  import SearchSummary from '$lib/SearchSummary.svelte';
  import Templates from '$lib/TemplateList.svelte';
  import NoResults from '$lib/NoResults.svelte';
  import Footer from '$lib/Footer.svelte';
  import Meta from '$lib/Meta.svelte';
  import type { Template } from '$src/Types';
  import type { PageData } from './$types';
  import { baseUrl } from '$src/constants';

  let { data }: { data: PageData } = $props();

  const description = 'A community-driven library of 400+ 1-click self-hosted apps and stacks, for easy use with Portainer or Docker-Compose';

  // Structured data identifying the site (escape < for safe inlining)
  const jsonLd = JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'Portainer Templates',
    url: baseUrl,
    description,
  }).replace(/</g, '\\u003c');

  const preSelectedCategories = page.url.searchParams.get('categories');

  let searchTerm = $state('');

  let selectedCategories = $state<string[]>(preSelectedCategories?.split(',') || []);

  let showCategories = $state(!!preSelectedCategories);

  const filteredTemplates = $derived(data.templates.filter((template: Template) => {
    const compareStr = (str1: string, str2: string) =>
      (str1 || '').toLowerCase().includes(str2.toLowerCase());

    if (selectedCategories.length) {
      const templateCategories = (template.categories || []).map((c) => c.toLowerCase());
      const hasSelectedCategory = selectedCategories.some((cat) =>
        templateCategories.includes(cat.toLocaleLowerCase())
      );
      if (!hasSelectedCategory) return false;
    }
    return (
      compareStr(template.title, searchTerm) ||
      compareStr(template.description, searchTerm) ||
      compareStr((template.categories || []).join(''), searchTerm)
    );
  }));

  const showHideCategoryList = () => {
    showCategories = !showCategories;
  };

  const toggleCategory = (category: string) => {
    if (selectedCategories.includes(category)) {
      selectedCategories = selectedCategories.filter((cat) => cat !== category);
    } else {
      selectedCategories = [...selectedCategories, category];
    }
  };

  const clearSearch = () => {
    searchTerm = '';
    selectedCategories = [];
  }

</script>

<Meta title="Portainer Templates" {description} />

<svelte:head>
  {@html '<script type="application/ld+json">' + jsonLd + '</scr' + 'ipt>'}
</svelte:head>

<!-- Main title, and CTA buttons -->
<Hero total={data.total} />

<!-- Search bar, and Templates sub-title -->
<ListFilter
  bind:searchTerm={searchTerm}
  toggleCategories={showHideCategoryList}
  isCategoriesVisible={showCategories}
/>

<!-- List of categories to filter by -->
{#if showCategories}
  <Categories
    categories={data.categories}
    selectedCategories={selectedCategories}
    toggleCategory={toggleCategory}
  />
{/if}

<!-- Text showing num results, and users search term + filters  -->
<SearchSummary
  searchTerm={searchTerm}
  selectedCategories={selectedCategories}
  clearSearch={clearSearch}
  numResults={filteredTemplates.length}
  totalResults={data.templates.length}
/>

<!-- List of available templates (filtered, if needed) -->
<Templates templates={filteredTemplates} />

<!-- If there are no templates matching search term, show lil message -->
{#if !filteredTemplates.length}
  <NoResults />
{/if}

