<script lang="ts">
let { searchTerm, selectedCategories, clearSearch, numResults, totalResults }: {
  searchTerm: string;
  selectedCategories: string[];
  clearSearch: () => void;
  numResults: number;
  totalResults: number;
} = $props();
</script>

{#if searchTerm || selectedCategories.length}
  <div class="search-summary">
    {#if searchTerm}
      <p>
        Showing {numResults} of {totalResults}
        results, matching "<i>{searchTerm}</i>"
        {selectedCategories.length  ? `in categories: ${selectedCategories.join(', ')}` : ''}
      </p>
    {:else}
      <p>
        Showing {numResults} of {totalResults}
        results, matching categories: {selectedCategories.join(', ')}
      </p>
    {/if}
    <button onclick={clearSearch}>⨯ Clear Filters</button>
  </div>
{/if}

<style lang="scss">
.search-summary {
  margin: 0 1rem;
  
  font-size: 0.9rem;
  display: flex;
  gap: 1rem;
  align-items: center;
  p {
    opacity: 0.75;
    margin: 0;
  }
  button {
    background: var(--gradient);
    outline: none;
    border: none;
    padding: 0.25rem 0.5rem;
    border-radius: 6px;
    color: var(--foreground);
    font-weight: 800;
    cursor: pointer;
    transition: all 0.2s ease-in-out;
    &:hover {
      transform: scale(1.1);
    }
  }
}
</style>