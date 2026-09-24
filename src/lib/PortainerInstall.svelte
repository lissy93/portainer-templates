<script lang="ts">
  // page-wide code theme, ReverseProxy and friends rely on this injection
  import codeHighlighting from 'svelte-highlight/styles/dracula';
  import yamlHighlight from 'svelte-highlight/languages/yaml';
  import bashHighlight from 'svelte-highlight/languages/bash';
  import CodeBlock from '$lib/CodeBlock.svelte';
  import { appSlug } from '$src/utils/template-to-docker-parser';
  import { templatesUrl, gitHubRepo } from '$src/constants';
  import type { Template, ProjectStats } from '$src/Types';

  let { heading = 'h2', template = null, stackfile = null, project = null }: {
    heading?: 'h1' | 'h2';
    template?: Template | null;
    stackfile?: string | null;
    project?: ProjectStats | null;
  } = $props();

  const copyToClipboard = (content: string) => {
    navigator.clipboard.writeText(content);
  };

  const repo = $derived(template?.repository);
  const repoDir = $derived(repo?.url.replace(/\.git$/, '').split('/').filter(Boolean).pop() ?? '');
  const cloneCommand = $derived(template && repo
    ? `git clone ${repo.url}\ncd ${repoDir}\n` + (template.type === 2
        ? `docker stack deploy -c ${repo.stackfile} ${appSlug(template)}`
        : `docker compose -f ${repo.stackfile} up -d`)
    : '');
</script>

<svelte:head>
  {@html codeHighlighting}
</svelte:head>

<section>
  <svelte:element this={heading} class="title">Install on Portainer</svelte:element>
  <p class="intro">Import all app templates into your Portainer instance, for easy 1-click deploys</p>
  <ol>
    <li>
      Ensure both
      <a href="https://docs.docker.com/engine/install/">Docker</a> and
      <a href="https://www.portainer.io/installation/">Portainer</a> are installed, and up-to-date
    </li>
    <li>Log into your Portainer web UI</li>
    <li>Under Settings → App Templates, paste the below URL</li>
    <li>Head to Home → App Templates, and the list of apps will show up</li>
    <li>Select {template?.title ?? 'the app you wish to deploy'}, fill in any config options, and hit Deploy</li>
  </ol>
  <h4>Template Import URL</h4>
  <pre class="template-url">{templatesUrl}</pre>
  <button onclick={() => copyToClipboard(templatesUrl)}>Copy</button>
  <details>
    <summary>Show Me</summary>
    <img class="demo" loading="lazy" src="https://cdn.as93.net/project-screens/portainer-templates-installation" alt="demo" />
  </details>

  {#if stackfile && repo}
    <details class="stackfile">
      <summary>Original stackfile</summary>
      <p>The {template?.type === 2 ? 'swarm stack' : 'compose'} file this template deploys, straight from its repo:</p>
      <CodeBlock code={stackfile} language={yamlHighlight} />
      <p>Or deploy it directly from the source:</p>
      <CodeBlock code={cloneCommand} language={bashHighlight} />
    </details>
  {/if}

  {#if template}
    <p class="more">
      More install options in our <a href={gitHubRepo}>documentation</a>{#if project?.url}, or see
      <a href={project.url} target="_blank" rel="noreferrer">{project.repo}</a> for app-specific guidance{/if}.
    </p>
  {/if}
</section>

<style lang="scss">
  section {
    background: var(--card);
    padding: 1rem;
    border-radius: 6px;
    margin: 1rem auto;
    max-width: 1000px;
    .title {
      margin: 0 0 0.5rem;
      font-size: 2rem;
    }
    .intro {
      margin: 0;
      font-size: 1.1rem;
      opacity: 0.5;
      font-style: italic;
    }
    p {
      margin: 0;
    }
    ol {
      margin: 0.5rem;
      padding: 0;
      list-style: none;
      li {
        counter-increment: item;
      }
      li:before {
        content: counter(item);
        color: var(--accent);
        margin-right: 0.5rem;
        font-weight: 600;
        width: 1ch;
        text-align: center;
        display: inline-block;
      }
    }
    h4 {
      margin: 0.5rem 0;
    }
    pre {
      background: var(--card-2);
      padding: 0.25rem 0.5rem;
      font-size: 1.1rem;
      width: fit-content;
      margin: 0.5rem 0;
      display: inline;
      border-radius: 6px;
      &.template-url {
        white-space: normal;
        overflow-wrap: anywhere;
      }
    }
    button {
      background: var(--background);
      padding: 0.25rem 0.5rem;
      border-radius: 6px;
      border: none;
      color: var(--foreground);
      font-family: Kanit;
      font-size: 1.1rem;
      cursor: pointer;
      transition: all 0.2s ease-in-out;
      &:hover {
        background: var(--gradient);
        transform: scale(1.1) rotate(-1deg);
      }
    }
    a {
      color: var(--accent);
    }
    .demo {
      display: block;
      margin: 0.5rem auto;
      border-radius: 6px;
      max-width: min(100%, 50rem);
    }
    details summary {
      cursor: pointer;
      font-weight: bold;
      width: fit-content;
      &:hover {
        color: var(--accent);
      }
    }
    .stackfile {
      margin: 1rem 0 0;
      p {
        margin: 0.5rem 0 0;
      }
    }
    .more {
      margin: 1rem 0 0;
      font-size: 0.9rem;
      opacity: 0.8;
    }
  }
</style>
