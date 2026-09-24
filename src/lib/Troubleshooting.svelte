<script lang="ts">
  import { gitHubRepo } from '$src/constants';
  import { formatDate, inlineMarkdown } from '$lib/format';
  import { envValue } from '$src/utils/template-to-docker-parser';
  import type { Template, Service, DockerMeta, ProjectStats, TemplateStatus } from '$src/Types';
  import Collapsible from '$lib/Collapsible.svelte';

  let { template, dockerMeta = null, project = null, services = [], status = null }: {
    template: Template;
    dockerMeta?: DockerMeta | null;
    project?: ProjectStats | null;
    services?: Service[];
    status?: TemplateStatus | null;
  } = $props();

  const repoLink = (repoUrl?: string | null): { slug: string; href: string } | null => {
    if (!repoUrl) return null;
    try {
      const url = new URL(repoUrl);
      const [owner, repo] = url.pathname.split('/').filter(Boolean);
      if (!url.hostname.endsWith('github.com') || !owner || !repo) return null;
      const slug = `${owner}/${repo.replace(/\.git$/i, '')}`;
      return { slug, href: `https://github.com/${slug}/issues/new` };
    } catch {
      return null;
    }
  };

  type PortMap = { host: string; container: string; proto: string };

  // keeps only numeric host ports, drops ${VAR} interpolations and non-strings from stackfiles
  const parsePorts = (ports: string[] = []): PortMap[] =>
    ports.filter((p) => typeof p === 'string').flatMap((port) => {
      const [mapping, proto = 'tcp'] = port.split('/');
      const parts = mapping.split(':');
      const [host, container] = parts.slice(-2);
      if (parts.length < 2 || !/^\d+(-\d+)?$/.test(host)) return [];
      return [{ host: host.split('-')[0], container: container.split('-')[0], proto }];
    });

  const sources = $derived(services.length > 1 ? services : [template]);
  const hostPorts = $derived(sources.flatMap((s) => parsePorts(s.ports)));
  const unmappedPorts = $derived(
    sources.flatMap((s) => (s.ports ?? []).filter((p) => typeof p === 'string' && !p.split('/')[0].includes(':'))),
  );
  const webPort = $derived(
    hostPorts.find((p) => ['80', '443', '8080', '3000', '8000'].includes(p.container)) ??
      hostPorts.find((p) => p.proto === 'tcp') ??
      null,
  );
  const webScheme = $derived(webPort?.container === '443' ? 'https' : 'http');

  const volumes = $derived(sources.flatMap((s) => s.volumes ?? []));
  const binds = $derived([...new Set(volumes.map((v) => v.bind ?? '').filter(Boolean))]);
  const bindPaths = $derived(binds.filter((b) => /^[/~]/.test(b)));
  const relativeBinds = $derived(binds.filter((b) => b.startsWith('./') || b.startsWith('../')));
  const roPaths = $derived([
    ...new Set(volumes.filter((v) => v.readonly && v.bind && !v.bind.endsWith('.sock')).map((v) => v.bind ?? '')),
  ]);
  const sockBinds = $derived(bindPaths.filter((b) => b.endsWith('.sock')));
  // paths where chown advice makes sense: writable, and not a socket
  const dataBinds = $derived(bindPaths.filter((b) => !b.endsWith('.sock') && !roPaths.includes(b)));

  const allEnv = $derived(sources.flatMap((s) => s.env ?? []));
  const requiredEnv = $derived([
    ...new Map(allEnv.filter((e) => !e.preset && !envValue(e)).map((e) => [e.name, e])).keys(),
  ]);
  const puidEnv = $derived(allEnv.find((e) => e.name === 'PUID'));
  const pgidEnv = $derived(allEnv.find((e) => e.name === 'PGID'));
  const puid = $derived((puidEnv && envValue(puidEnv)) || '1000');
  const pgid = $derived((pgidEnv && envValue(pgidEnv)) || '1000');

  const appName = $derived(template.name ?? services.find((s) => s.name)?.name);
  const image = $derived(template.image ?? services.find((s) => s.image)?.image ?? null);
  const usesLatest = $derived(!!image && (image.match(/:([^/:]+)$/)?.[1] ?? 'latest') === 'latest');
  const archs = $derived(dockerMeta?.architectures ?? []);

  const isStack = $derived(template.type !== 1);
  const restartPolicy = $derived(template.restart_policy ?? services.find((s) => s.restart_policy)?.restart_policy);
  const restartMasks = $derived(restartPolicy === 'always' || restartPolicy === 'unless-stopped');
  // stack containers get prefixed names, so only suggest the template name for plain containers
  const containerRef = $derived((!isStack && appName) || '<container>');
  const inspectCmd = $derived(`docker inspect ${containerRef} --format '{{.State.ExitCode}}'`);
  const hostNetwork = $derived(template.network === 'host');
  const customNetwork = $derived(
    template.network && !['bridge', 'host', 'none'].includes(template.network) ? template.network : null,
  );
  const noVolumes = $derived(template.type === 1 && !!image && volumes.length === 0);

  const reviewed = $derived(formatDate(status?.updated ?? ''));

  const rows = $derived([
    { label: 'Bug within the app', link: repoLink(project?.url), fallback: `Open an issue within ${appName || 'the app'}'s repo` },
    { label: 'Template not working', link: repoLink(template.maintainer), fallback: "Open an issue within the template's repo" },
    { label: 'This website not working', link: repoLink(gitHubRepo), fallback: '' },
  ]);
</script>

<Collapsible title="Troubleshooting">
  <div class="troubleshooting">
      {#if status}
        <div class="troubleshooting-item">
          <h3>Known issue</h3>
          <p>This template is currently marked as {status.status}, so it may not deploy or run as expected{reviewed ? ` (last reviewed ${reviewed})` : ''}.</p>
          <ul>
            {#if status.note}<li>{@html inlineMarkdown(status.note)}</li>{/if}
            <li>Until it's fixed, one of the similar apps below may work as an alternative.</li>
          </ul>
        </div>
      {/if}

      <div class="troubleshooting-item">
        <h3>Check the logs first</h3>
        <p>Nine times out of ten the logs tell you exactly what went wrong.</p>
        <ul>
          <li>In Portainer, go to Containers, click the container, then Logs. Or run <code>docker logs {containerRef}</code></li>
          <li>Exit codes help too: <code>137</code> means killed, usually out of memory. <code>126</code> or <code>127</code> means the command inside the image is broken.</li>
        </ul>
      </div>

      {#if hostPorts.length && !hostNetwork}
        <div class="troubleshooting-item">
          <h3>Port already in use</h3>
          <p>
            If deployment fails with "Bind for 0.0.0.0:{hostPorts[0].host} failed: port is already allocated",
            something else on your server is using that port.
          </p>
          <ul>
            <li>Find what's using it: <code>sudo ss -tlnp | grep :{hostPorts[0].host}</code></li>
            <li>
              Stop the other service, or pick a different host port. In <code>{hostPorts[0].host}:{hostPorts[0].container}</code>
              only the left number is yours to change, the right one belongs to the app.
            </li>
          </ul>
        </div>
      {/if}

      {#if hostNetwork}
        <div class="troubleshooting-item">
          <h3>Runs on the host network</h3>
          <p>This container shares your server's network directly, so port mappings are ignored and every port the app opens binds straight to the host.</p>
          <ul>
            <li>
              If a port won't bind, find the clash with <code>sudo ss -tlnp</code> and stop the other service,
              or change the port in {appName || 'the app'}'s own settings.
            </li>
          </ul>
        </div>
      {/if}

      {#if unmappedPorts.length && !hostNetwork}
        <div class="troubleshooting-item">
          <h3>Published on a random port</h3>
          <p>
            This template exposes <code>{unmappedPorts[0]}</code> without setting a host port,
            so Docker picks a random free one on every deploy.
          </p>
          <ul>
            <li>Find it in the Ports column of Portainer's container list, or with <code>docker port {containerRef}</code></li>
          </ul>
        </div>
      {/if}

      {#if webPort}
        <div class="troubleshooting-item">
          <h3>Running but the page won't load</h3>
          <p>The container is up but nothing appears in your browser.</p>
          <ul>
            <li>Use your server's real IP: <code>{webScheme}://your-server-ip:{webPort.host}</code>. The 0.0.0.0 link Portainer shows isn't a real address.</li>
            <li>Give it a minute after first deploy, {appName || 'some apps'} can take a while to initialise.</li>
            <li>Make sure your firewall allows the port, e.g. <code>sudo ufw allow {webPort.host}</code></li>
          </ul>
        </div>
      {/if}

      {#if dataBinds.length || roPaths.length}
        <div class="troubleshooting-item">
          <h3>Permission denied on volumes</h3>
          <p>If the logs show "permission denied", the app can't write to its data folder on the host.</p>
          <ul>
            {#if dataBinds.length}
              <li>
                Fix the ownership: <code>sudo chown -R {puid}:{pgid} {dataBinds[0]}</code>
                {#if dataBinds.length > 1}(and the same for the other mapped folders){/if}
              </li>
            {/if}
            {#if puidEnv}
              <li>
                Or set the <code>PUID</code> and <code>PGID</code> variables (defaults {puid}:{pgid}) to match your
                own user, found with <code>id $USER</code>
              </li>
            {/if}
            {#if roPaths.length}
              <li>
                Seeing "read-only file system"? <code>{roPaths[0]}</code> is mounted read-only on purpose,
                the app isn't meant to write there.
              </li>
            {/if}
          </ul>
        </div>
      {/if}

      {#if sockBinds.length}
        <div class="troubleshooting-item">
          <h3>Can't reach the Docker socket</h3>
          <p>
            {appName || 'This app'} talks to Docker through <code>{sockBinds[0]}</code>. If the logs show
            "permission denied while trying to connect to the Docker daemon socket", the app's user can't access it.
          </p>
          <ul>
            <li>Check the socket exists on the host: <code>ls -l /var/run/docker.sock</code></li>
            <li>Run the container as root, or add the docker group's id to the container with <code>group_add</code>.</li>
          </ul>
        </div>
      {/if}

      {#if image}
        <div class="troubleshooting-item">
          <h3>Image won't pull</h3>
          <p>Test the pull directly on the host: <code>docker pull {image}</code></p>
          <ul>
            <li>
              "manifest unknown" means the tag no longer exists.
              {#if usesLatest}This template uses <code>latest</code>, so try pinning a specific version instead.{/if}
            </li>
            <li>"toomanyrequests" is the Docker Hub rate limit. Log in with <code>docker login</code> to raise it.</li>
            <li>"no space left on device" means a full disk. Reclaim space with <code>docker system prune</code></li>
          </ul>
        </div>

        <div class="troubleshooting-item">
          <h3>"exec format error"</h3>
          <p>This means the image was built for a different CPU architecture than your server.</p>
          <ul>
            {#if archs.length}
              <li>This image supports: <code>{archs.join(', ')}</code></li>
            {/if}
            <li>Check yours with <code>uname -m</code>: x86_64 is amd64, aarch64 is arm64. Raspberry Pi and other ARM boards are the usual culprits.</li>
          </ul>
        </div>
      {/if}

      {#if restartMasks}
        <div class="troubleshooting-item">
          <h3>Container keeps restarting</h3>
          <p>The <code>{restartPolicy}</code> restart policy relaunches the app after every crash, so the real error can scroll past.</p>
          <ul>
            <li>Check the logs right after a restart, the last few lines before it died are the useful ones.</li>
            <li>Get the exit code with <code>{inspectCmd}</code></li>
            <li>Still stuck? Redeploy once with the restart policy set to <code>no</code> so the failure stays visible.</li>
          </ul>
        </div>
      {/if}

      {#if noVolumes}
        <div class="troubleshooting-item">
          <h3>Data disappears when the container is recreated</h3>
          <p>This template doesn't define any volumes, so everything {appName || 'the app'} saves lives inside the container and is lost on update or recreate.</p>
          <ul>
            <li>Add a volume mapping for {appName || 'the app'}'s data folder before storing anything you care about.</li>
          </ul>
        </div>
      {/if}

      {#if customNetwork}
        <div class="troubleshooting-item">
          <h3>Network "{customNetwork}" not found</h3>
          <p>This template attaches to the <code>{customNetwork}</code> network, which must already exist on your host.</p>
          <ul>
            <li>Create it first with <code>docker network create {customNetwork}</code>, then redeploy.</li>
          </ul>
        </div>
      {/if}

      {#if requiredEnv.length}
        <div class="troubleshooting-item">
          <h3>Required settings are blank</h3>
          <p>
            <code>{requiredEnv.join(', ')}</code>
            {requiredEnv.length > 1 ? 'have' : 'has'} no default value, and {appName || 'the app'} may crash or misbehave if left empty.
          </p>
          <ul>
            <li>Fill {requiredEnv.length > 1 ? 'them' : 'it'} in on the deploy screen before hitting deploy.</li>
          </ul>
        </div>
      {/if}

      {#if isStack}
        <div class="troubleshooting-item">
          <h3>Stack won't deploy</h3>
          <p>Compose stacks fail fast on small mistakes, and Portainer shows the reason just above the editor.</p>
          <ul>
            <li>YAML only accepts spaces for indentation, a single tab breaks the whole file.</li>
            {#if relativeBinds.length}
              <li>
                Relative volume paths like <code>{relativeBinds[0]}</code> often fail in Portainer because there's no
                working directory. Swap them for absolute paths.
              </li>
            {/if}
          </ul>
        </div>
      {/if}

      {#if template.privileged}
        <div class="troubleshooting-item">
          <h3>Privileged mode</h3>
          <p>This template runs the container in privileged mode, giving it full access to your host.</p>
          <ul>
            <li>Only deploy it if you trust the app.</li>
            <li>If deployment is blocked, your Portainer security settings or hardened host may not allow privileged containers.</li>
          </ul>
        </div>
      {/if}

      {#if project?.archived}
        <div class="troubleshooting-item">
          <h3>Upstream project is archived</h3>
          <p>The developers have archived <code>{project.repo}</code>, so bugs and security issues won't be fixed.</p>
          <ul>
            <li>It'll keep working for now, but consider the similar apps below for a maintained alternative.</li>
          </ul>
        </div>
      {/if}

      <div class="troubleshooting-item">
        <h3>Raise an issue</h3>
        <p>Found something which isn't working as it should? Here's how to report it.</p>
        <ul>
          {#each rows as row (row.label)}
            <li>
              <strong>{row.label}:</strong>
              {#if row.link}
                Open an issue on <a href={row.link.href} target="_blank" rel="noreferrer">{row.link.slug}</a>
              {:else}
                {row.fallback}
              {/if}
            </li>
          {/each}
        </ul>
      </div>
  </div>
</Collapsible>

<style lang="scss">
  .troubleshooting {
    .troubleshooting-item {
      &:not(:last-child) {
        padding-bottom: 1rem;
        border-bottom: 2px solid var(--background);
        margin-bottom: 1rem;
      }
      h3 {
        margin: 0;
        font-size: 1.4rem;
        font-weight: 500;
      }
      p {
        margin: 0 0 0.25rem;
      }
      ul {
        margin: 0;
        padding-left: 1.25rem;
        li {
          strong {
            font-weight: 500;
          }
        }
      }
      a {
        color: var(--accent);
      }
      code {
        background: var(--background);
        padding: 0.1em 0.4em;
        border-radius: 4px;
        font-size: 0.95em;
        overflow-wrap: anywhere;
      }
    }
  }
</style>
