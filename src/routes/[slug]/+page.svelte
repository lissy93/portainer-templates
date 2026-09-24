<script lang="ts">

  import { page } from '$app/state';
  import snarkdown from 'snarkdown';

  import ServiceStats from '$lib/ServiceStats.svelte';
  import DockerStats from '$lib/DockerStats.svelte';
  import ProjectStats from '$lib/ProjectStats.svelte';
  import Versions from '$lib/Versions.svelte';
  import SimilarApps from '$lib/SimilarApps.svelte';
  import DeployModes from '$lib/DeployModes.svelte';
  import MdContent from '$lib/MdContent.svelte';
  import Note from '$lib/Note.svelte';
  import Logo from '$lib/Logo.svelte';
  import InstallSection from '$lib/configurator/InstallSection.svelte';
  import PortainerInstall from '$lib/PortainerInstall.svelte';
  import ReverseProxy from '$lib/ReverseProxy.svelte';
  import Troubleshooting from '$lib/Troubleshooting.svelte';
  import PortainerExplainer from '$lib/PortainerExplainer.svelte';
  import Meta from '$lib/Meta.svelte';
  import Button from '$lib/Button.svelte';

  import { baseUrl } from '$src/constants';
  import { baseTitle } from '$lib/format';
  import type { Template, Service, DockerHubResponse, DockerMeta, ProjectStats as ProjectStatsType, SimilarApp, DeployMode } from '$src/Types';

  const urlSlug = $derived(page.params.slug ?? '');

  const template = $derived(page.data.template as Template);
  const dockerStats = $derived(page.data.dockerStats as DockerHubResponse | null);
  const dockerMeta = $derived(page.data.dockerMeta as DockerMeta | null);
  const project = $derived(page.data.project as ProjectStatsType | null);
  const services = $derived((page.data.services ?? []) as Service[]);
  const similar = $derived((page.data.similar ?? []) as SimilarApp[]);
  const modes = $derived((page.data.modes ?? []) as DeployMode[]);
  // split "Airsonic (container)" so the variant can sit quieter than the name
  const titleName = $derived(baseTitle(template?.title ?? ''));
  const titleVariant = $derived((template?.title ?? '').slice(titleName.length).trim());
  const readme = $derived((page.data.readme ?? null) as string | null);
  const stackfile = $derived((page.data.stackfile ?? null) as string | null);
  const issuesUrl = $derived((page.data.issuesUrl ?? null) as string | null);

  const makeMultiDoc = (svcs: Service[]) =>
    svcs
      .filter((s) => s?.dockerStats?.full_description)
      .map((s) => ({
        name: s.name,
        description: s.dockerStats?.description ?? '',
        content: s.dockerStats?.full_description ?? '',
      }));

  const multiDocs = $derived(makeMultiDoc(services));

  // Only link out to attribution URLs we can vouch for (http/https, nothing funny)
  const safeHref = (url?: string): string | null => {
    if (!url) return null;
    try {
      const parsed = new URL(url);
      return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.href : null;
    } catch {
      return null;
    }
  };
  const maintainerHref = $derived(safeHref(template.maintainer));
  const sourceHref = $derived(safeHref(template.repository?.url));
  const maintainerName = $derived.by(() => {
    if (!maintainerHref) return '';
    const url = new URL(maintainerHref);
    return url.hostname.endsWith('github.com')
      ? (url.pathname.split('/').filter(Boolean)[0] ?? url.hostname)
      : url.hostname.replace(/^www\./, '');
  });

  // Front-load the install intent so it survives Google's ~155 char cut, then let the app's own blurb through
  const makeMetaDescription = (t: Template) =>
    `How to install ${t.title} with Docker, Docker Compose, Portainer, Kubernetes or Podman. ${t.description}`;

  // Latest published tag, ignoring the rolling "latest" alias which isn't a real version
  const latestVersion = $derived.by(() => {
    const v = dockerMeta?.latestVersion ?? project?.latestRelease ?? '';
    return v && v.toLowerCase() !== 'latest' ? v : '';
  });

  // The upstream app author is the repo owner, not the template maintainer
  const appAuthor = $derived.by(() => {
    if (!project) return null;
    const owner = project.repo.split('/')[0] || project.repo;
    return { '@type': 'Organization', name: owner, url: project.url };
  });

  // escape < so the JSON can't break out of the script tag
  const escapeLd = (obj: unknown) => JSON.stringify(obj).replace(/</g, '\\u003c');

  const jsonLd = $derived(escapeLd({
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: template.title,
    description: template.description,
    applicationCategory: template.categories?.[0] ?? 'DeveloperApplication',
    operatingSystem: 'Linux',
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
    url: `${baseUrl}/${urlSlug}`,
    ...(template.logo ? { image: template.logo } : {}),
    ...(latestVersion ? { softwareVersion: latestVersion } : {}),
    ...(sourceHref ? { downloadUrl: sourceHref } : {}),
    ...(project?.releasedAt ? { datePublished: project.releasedAt } : {}),
    ...(project?.updatedAt ? { dateModified: project.updatedAt } : {}),
    ...(appAuthor ? { author: appAuthor } : {}),
  }));

  // Mirrors the visible "Install on Portainer" steps, so the markup matches what's on the page
  const howToLd = $derived(escapeLd({
    '@context': 'https://schema.org',
    '@type': 'HowTo',
    name: `How to install ${template.title} with Portainer`,
    description: `Deploy ${template.title} on your own server using Portainer's one-click app templates.`,
    ...(template.logo ? { image: template.logo } : {}),
    totalTime: 'PT5M',
    step: [
      { '@type': 'HowToStep', position: 1, name: 'Install Docker and Portainer', text: 'Ensure both Docker and Portainer are installed and up to date.' },
      { '@type': 'HowToStep', position: 2, name: 'Log into Portainer', text: 'Log into your Portainer web UI.' },
      { '@type': 'HowToStep', position: 3, name: 'Add the template URL', text: 'Under Settings → App Templates, paste the Portainer Templates import URL.' },
      { '@type': 'HowToStep', position: 4, name: 'Open App Templates', text: 'Head to Home → App Templates, and the list of apps appears.' },
      { '@type': 'HowToStep', position: 5, name: `Deploy ${template.title}`, text: `Select ${template.title}, fill in any config options, and hit Deploy.` },
    ],
  }));

</script>

<svelte:head>
  {@html '<script type="application/ld+json">' + jsonLd + '</scr' + 'ipt>'}
  {@html '<script type="application/ld+json">' + howToLd + '</scr' + 'ipt>'}
</svelte:head>

<Meta
  title="Install {template.title} with Docker, Compose & Portainer"
  description={makeMetaDescription(template)}
  path="/{urlSlug}"
  image={template.logo}
/>

{#if template}
  <section class="summary-section">
    <div class="summary-head">
      <h1>
        <Logo src={template.logo} name={template.title} />
        <span>{titleName}{#if titleVariant}{' '}<span class="variant">{titleVariant}</span>{/if}</span>
      </h1>
      <DeployModes {modes} />
    </div>
    {#if template.categories}
      <p class="tags">
        {#each template.categories as tag (tag)}
          <a href="/?categories={tag}"><span>{tag}</span></a>
        {/each}
      </p>
    {/if}
    <div class="content">
      <div class="left">
        <p class="description">{@html snarkdown(template.description)}</p>
        {#if (dockerStats && dockerStats.name) || project}
          <div class="details">
            {#if dockerStats && dockerStats.name}
              <DockerStats info={dockerStats} meta={dockerMeta} />
            {/if}
            {#if project}
              <ProjectStats {project} />
            {/if}
          </div>
        {/if}
      </div>
      <ServiceStats template={template} />
    </div>
    {#if maintainerHref || sourceHref || issuesUrl}
      <div class="summary-foot">
        <p class="attribution">
          {#if maintainerHref}Template by <a href={maintainerHref} target="_blank" rel="noreferrer">{maintainerName}</a>{/if}{#if maintainerHref && sourceHref} · {/if}{#if sourceHref}<a href={sourceHref} target="_blank" rel="noreferrer">Source</a>{/if}
        </p>
        {#if issuesUrl}
          <Button to={issuesUrl} target="_blank" icon="bug" size="small" title="Report a problem with this template to its maintainers">Report issue</Button>
        {/if}
      </div>
    {/if}
  </section>

  {#if template.note}
    <Note note={template.note} />
  {/if}

  {#if services.length > 1}
    <section class="service-section">
      <h2>Services</h2>
      <div class="service-list">
        {#each services as service (service.name)}
          <div class="service-each">
          <h3>{service.name}</h3>
          <div class="service-data">
            <ServiceStats template={service} />
            {#if service.dockerStats && service.dockerStats.name}
              <DockerStats info={service.dockerStats} />
            {/if}
          </div>
        </div>
        {/each}
      </div>
    </section>
  {/if}

  <InstallSection {template} {services} meta={dockerMeta} />
  <PortainerInstall {template} {stackfile} {project} />

  {#if dockerStats?.full_description}
    <MdContent content={dockerStats.full_description} />
  {:else if multiDocs.length > 0}
    <MdContent multiContent={multiDocs} />
  {:else if readme}
    <MdContent content={readme} title="Project Documentation" />
  {/if}

  <Versions versions={dockerMeta?.versions ?? []} />
  <svelte:boundary onerror={(e) => console.error('Reverse proxy section failed:', e)}>
    <ReverseProxy {template} {services} />
  </svelte:boundary>
  <svelte:boundary onerror={(e) => console.error('Troubleshooting section failed:', e)}>
    <Troubleshooting {template} {dockerMeta} {project} {services} />
  </svelte:boundary>
  <svelte:boundary onerror={(e) => console.error('Portainer explainer section failed:', e)}>
    <PortainerExplainer {template} {dockerMeta} {project} {services} />
  </svelte:boundary>
  <SimilarApps items={similar} />

{/if}


<style lang="scss">
  section {
    max-width: 1000px;
    margin: 1rem auto;
  }

  .summary-section {
    background: var(--card);
    border-radius: 6px;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    .summary-head {
      display: flex;
      flex-wrap: wrap;
      align-items: flex-start;
      justify-content: space-between;
      gap: 0.75rem 1rem;
    }
    h1 {
      font-size: 4rem;
      margin: 0;
      display: flex;
      align-items: center;
      gap: 1rem;
      .variant {
        font-size: 0.45em;
        font-weight: 400;
        opacity: 0.6;
        white-space: nowrap;
      }
    }
    .tags {
      display: flex;
      margin: 0;
      gap: 0.5rem;
      a {
        color: var(--foreground);
        text-decoration: none;
        transition: all 0.2s ease-in-out;
        span {
          &:before {
            content: '#';
            opacity: 0.5;
          }
          &:not(:last-child)::after {
            content: ',';
            margin-right: 0.5rem;
          }
        }
        &:hover {
          color: var(--accent);
          transform: scale(1.08);
        }
      }
    }
  }

  .content {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    justify-content: space-between;
    margin-top: 1rem;
    > :global(.stats) {
      min-width: 15rem;
      max-width: 18rem;
    }
    .left {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 1rem;
      .details {
        display: flex;
        flex-direction: column;
        gap: 1rem;
        @media (min-width: 1080px) {
          flex-direction: row;
          flex-wrap: wrap;
          align-items: stretch;
          > :global(.stats) {
            flex: 1 1 15rem;
          }
        }
      }
    }
    p.description {
      background: var(--card-2);
      padding: 1rem;
      border-radius: 6px;
      margin: 0;
      :global(a) { color: var(--accent); }
    }
  }

  .summary-foot {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem 1rem;
    margin-top: 1rem;
    > :global(a) {
      background: var(--card-2);
      margin-left: auto;
      :global(svg) {
        width: 13px;
        height: 13px;
      }
    }
  }

  .attribution {
    margin: 0;
    font-size: 0.85rem;
    opacity: 0.6;
    a {
      color: inherit;
      text-decoration: underline;
      &:hover { color: var(--accent); }
      &:not(:last-child) { margin-right: 0.25rem; }
      &:last-child { margin-left: 0.25rem; }
    }
  }

  .service-section {
    background: var(--card);
    border-radius: 6px;
    padding: 1rem;
    h2 {
      margin: 0;
      font-size: 2rem;
    }
    .service-list {
      display: flex;
      flex-direction: column;
      gap: 2rem;
      h3 {
        margin: 0.5rem 0;
        font-weight: 400;
        font-size: 2rem;
      }
      .service-each .service-data {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(min(16rem, 100%), 1fr));
        gap: 1rem;
        > :global(.stats) {
          min-width: 0;
        }
      }
    }
  }
</style>
