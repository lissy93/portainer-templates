<script lang="ts">
  import { goto } from '$app/navigation';

  let {
    searchTerm = $bindable(''),
    isCategoriesVisible,
    toggleCategories,
  }: {
    searchTerm: string;
    isCategoriesVisible: boolean;
    toggleCategories: () => void;
  } = $props();

  const onEnter = (e: KeyboardEvent) => {
    if (e.key !== 'Enter') return;
    const term = searchTerm.trim();
    goto(term ? `/search?q=${encodeURIComponent(term)}` : '/search');
  };
</script>

<div class="title-row">
  <div class="heading">
    <h2>Template List</h2>
    <p>Click an app to view info, stats and usage docs</p>
  </div>
  <div class="filters">
    <button onclick={toggleCategories}>
      {isCategoriesVisible ? '▲' : '▼'} Categories
    </button>
    <span class="search">
      <input
        type="text"
        placeholder="Search..."
        aria-label="Search templates"
        aria-describedby="search-hint"
        enterkeyhint="search"
        bind:value={searchTerm}
        onkeydown={onEnter}
      />
      <small id="search-hint">Press Enter for advanced search</small>
    </span>
  </div>
</div>

<style lang="scss">
.title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 1rem auto 0.5rem auto;
  padding: 0 1rem;
  max-width: var(--max-width);
  flex-wrap: wrap;
  h2 {
    font-size: 2rem;
    margin: 0;
  }
  .heading p {
    margin: 0;
    font-size: 0.9rem;
    opacity: 0.75;
  }
  .filters {
    input {
      background: var(--card);
      border: 1px solid transparent;
      color: var(--foreground);
      padding: 0.5rem 0.75rem;
      border-radius: 6px;
      transition:all 0.3s ease-in-out;
      &:focus, &:hover {
        box-shadow: var(--shadow);
      }
    }
    .search {
      display: inline-flex;
      text-align: center;
      flex-direction: column;
      small {
        font-size: 0.7rem;
        opacity: 0.6;
        white-space: nowrap;
      }
    }
  }
  button {
    color: var(--foreground);
    border: 1px solid transparent;
    padding: 0 0.3rem;
    margin: 0.25rem;
    line-height: 2rem;
    border-radius: 6px;
    text-transform: capitalize;
    background: var(--card);
    transition: all 0.3s ease-in-out;
    cursor: pointer;
    font-size: 0.9rem;
    &:hover {
      background: var(--gradient);
    }
  }
}
</style>