<script lang="ts">
  import type { Snippet } from 'svelte';
  import snarkdown from 'snarkdown';
  import HelpTip from './HelpTip.svelte';
  import { patterns, secretEnv, emptyPort, emptyEnv, emptyVolume, emptyLabel, emptyDevice, ALL_FIELDS, type ServiceConfig, type MethodFields } from './config';

  let { config = $bindable(), nameRequired = false, imageRequired = false, fields = ALL_FIELDS, traefikKind = 'labels', envFileKind = 'env', extras }: {
    config: ServiceConfig;
    nameRequired?: boolean;
    imageRequired?: boolean;
    fields?: MethodFields;
    traefikKind?: 'labels' | 'ingress';
    envFileKind?: 'env' | 'secret' | null;
    extras?: Snippet;
  } = $props();

  const id = $props.id();
  let advanced = $state(false);
  let revealed = $state(-1);

  /* render a field description as markdown, but keep stray [brackets] as text (snarkdown turns them into dead links) */
  const renderDesc = (md: string) => snarkdown(md).replace(/<a href="undefined">(.*?)<\/a>/g, '[$1]');
  const domainPlaceholder = $derived(`${(config.name || 'app').toLowerCase().replace(/[^a-z0-9-]/g, '-')}.example.com`);
</script>

<div class="config-form">
  <fieldset class="panel">
    <legend>General</legend>
    <div class="grid">
      <label>
        <span>Container name <HelpTip for="name" /></span>
        <input type="text" bind:value={config.name} pattern={patterns.name} required={nameRequired}
          placeholder="my-app" title="What to call the container" spellcheck="false" autocomplete="off" />
      </label>
      {#if fields.restart}
        <label>
          <span>Restart policy <HelpTip for="restart" /></span>
          <select bind:value={config.restart} title="When the container should restart automatically">
            <option value="unless-stopped">Unless stopped</option>
            <option value="always">Always</option>
            <option value="on-failure">On failure</option>
            <option value="no">Never</option>
          </select>
        </label>
      {/if}
      {@render extras?.()}
    </div>
  </fieldset>

  <fieldset class="panel">
    <legend>Ports <HelpTip for="ports" /></legend>
    <div class="rows">
      {#each config.ports as port, i (i)}
        <div class="row ports">
          <input type="text" inputmode="numeric" bind:value={port.host} pattern={patterns.hostPort}
            placeholder="auto" aria-label="Host port" title="Port on the host (leave empty for a random one)"
            spellcheck="false" autocomplete="off" />
          <span class="sep" aria-hidden="true">:</span>
          <input type="text" inputmode="numeric" bind:value={port.container} pattern={patterns.containerPort}
            required={!!port.host} placeholder="80" aria-label="Container port" title="Port inside the container"
            spellcheck="false" autocomplete="off" />
          <select bind:value={port.protocol} aria-label="Protocol" title="TCP or UDP">
            <option value="tcp">tcp</option>
            <option value="udp">udp</option>
          </select>
          <button type="button" class="remove" onclick={() => config.ports.splice(i, 1)}
            aria-label="Remove port {port.container || i + 1}">&times;</button>
        </div>
      {/each}
      <button type="button" class="add" onclick={() => config.ports.push(emptyPort())}>+ Add port</button>
    </div>
  </fieldset>

  <fieldset class="panel">
    <legend>Environment variables <HelpTip for="env" /></legend>
    <div class="rows">
      {#each config.env as env, i (i)}
        <div class="row env">
          {#if env.fixed}
            <span class="key" title={env.name}>
              <span class="name">
                {env.label || env.name}
                {#if env.description}<HelpTip tip={renderDesc(env.description)} html align="right" />{/if}
              </span>
              {#if env.label && env.label !== env.name}<code>{env.name}</code>{/if}
            </span>
          {:else}
            <input type="text" bind:value={env.name} pattern={patterns.envName} required={!!env.value}
              placeholder="NAME" aria-label="Variable name" spellcheck="false" autocomplete="off" />
          {/if}
          {#if env.select}
            <select bind:value={env.value} disabled={env.preset} aria-label="Value for {env.name}">
              {#each env.select as opt (opt.value)}
                <option value={opt.value}>{opt.text}</option>
              {/each}
            </select>
          {:else}
            {@const masked = secretEnv(env.name) && !env.preset && revealed !== i}
            <input type={masked ? 'password' : 'text'} value={env.value}
              oninput={(e) => (env.value = e.currentTarget.value)}
              onfocus={() => (revealed = i)} onblur={() => (revealed = -1)}
              disabled={env.preset} placeholder="value"
              aria-label="Value for {env.name || 'new variable'}"
              title={env.preset ? 'Preset by the template' : undefined}
              spellcheck="false" autocomplete={masked ? 'new-password' : 'off'} />
          {/if}
          <button type="button" class="remove" onclick={() => config.env.splice(i, 1)}
            aria-label="Remove variable {env.name || i + 1}">&times;</button>
        </div>
      {/each}
      <button type="button" class="add" onclick={() => config.env.push(emptyEnv())}>+ Add variable</button>
    </div>
    {#if envFileKind && config.env.length}
      <label class="check" title={envFileKind === 'secret'
        ? 'Store the values in a Secret object instead of the pod spec'
        : 'Reference the values from a file instead of putting them in the config'}>
        <input type="checkbox" bind:checked={config.envFile} />
        {envFileKind === 'secret' ? 'Keep values in a Kubernetes Secret' : 'Keep values in a separate .env file'}
      </label>
    {/if}
  </fieldset>

  <fieldset class="panel">
    <legend>Volumes <HelpTip for="volumes" /></legend>
    <div class="rows">
      {#each config.volumes as vol, i (i)}
        <div class="row volumes">
          <input type="text" bind:value={vol.bind} pattern={patterns.volumeSource} placeholder="auto"
            aria-label="Host path or named volume" title="Host path or named volume (leave empty to let docker manage it)"
            spellcheck="false" autocomplete="off" />
          <span class="sep" aria-hidden="true">:</span>
          <input type="text" bind:value={vol.container} pattern={patterns.containerPath} required={!!vol.bind}
            placeholder="/data" aria-label="Container path" title="Path inside the container the data is mounted at"
            spellcheck="false" autocomplete="off" />
          <label class="check" title="Mount read-only">
            <input type="checkbox" bind:checked={vol.readonly} /> ro
          </label>
          <button type="button" class="remove" onclick={() => config.volumes.splice(i, 1)}
            aria-label="Remove volume {vol.container || i + 1}">&times;</button>
        </div>
      {/each}
      <button type="button" class="add" onclick={() => config.volumes.push(emptyVolume())}>+ Add volume</button>
    </div>
  </fieldset>

  <button type="button" class="advanced-toggle" aria-expanded={advanced} onclick={() => (advanced = !advanced)}>
    <span class="caret" class:open={advanced} aria-hidden="true">&#9656;</span>
    {advanced ? 'Hide' : 'Show'} advanced options
  </button>

  {#if advanced}
    <fieldset class="panel">
      <legend>Advanced</legend>
      <div class="grid">
        <label>
          <span>Image <HelpTip for="image" /></span>
          <input type="text" bind:value={config.image} pattern={patterns.image} required={imageRequired}
            placeholder="image:tag" title="Container image, with an optional tag" spellcheck="false" autocomplete="off" />
        </label>
        <label>
          <span>Network <HelpTip for="network" /></span>
          <input type="text" bind:value={config.network} pattern={patterns.network} list="{id}-networks"
            placeholder="bridge (default)" title="Docker network to join, or a network mode"
            spellcheck="false" autocomplete="off" />
        </label>
        <datalist id="{id}-networks">
          <option value="bridge"></option>
          <option value="host"></option>
          <option value="none"></option>
        </datalist>
        <label>
          <span>Hostname <HelpTip for="hostname" /></span>
          <input type="text" bind:value={config.hostname} pattern={patterns.hostname} placeholder="optional"
            title="Hostname inside the container" spellcheck="false" autocomplete="off" />
        </label>
        <label>
          <span>Entrypoint <HelpTip for="entrypoint" /></span>
          <input type="text" bind:value={config.entrypoint} placeholder="image default"
            title="Override the image entrypoint" spellcheck="false" autocomplete="off" />
        </label>
        <label>
          <span>Command <HelpTip for="command" /></span>
          <input type="text" bind:value={config.command} placeholder="image default"
            title="Override the image start command" spellcheck="false" autocomplete="off" />
        </label>
        <label>
          <span>User <HelpTip for="user" /></span>
          <input type="text" bind:value={config.user} pattern={patterns.user} placeholder="uid:gid"
            title="User (and optionally group) to run as" spellcheck="false" autocomplete="off" />
        </label>
        <label>
          <span>CPU limit <HelpTip for="cpus" /></span>
          <input type="text" inputmode="decimal" bind:value={config.cpus} pattern={patterns.cpus}
            placeholder="e.g. 1.5" title="Max CPUs the container can use" spellcheck="false" autocomplete="off" />
        </label>
        <label>
          <span>Memory limit <HelpTip for="memory" /></span>
          <input type="text" bind:value={config.memory} pattern={patterns.memory} placeholder="e.g. 512m"
            title="Max memory, like 512m or 2g" spellcheck="false" autocomplete="off" />
        </label>
        {#if fields.privileged}
          <label class="check boxed" title="Full access to the host, only enable if the app needs it">
            <input type="checkbox" bind:checked={config.privileged} /> Privileged mode
          </label>
        {/if}
        {#if fields.gpu}
          <label class="check boxed" title="Give the container access to NVIDIA GPUs">
            <input type="checkbox" bind:checked={config.gpu} /> NVIDIA GPU
          </label>
        {/if}
        {#if fields.interactive}
          <label class="check boxed" title="Keep stdin open and allocate a TTY">
            <input type="checkbox" bind:checked={config.interactive} /> Interactive TTY
          </label>
        {/if}
      </div>
    </fieldset>
    <fieldset class="panel">
      <legend>Traefik</legend>
      <label class="check">
        <input type="checkbox" bind:checked={config.traefik.enabled} />
        {traefikKind === 'ingress'
          ? 'Add an Ingress to serve this app on a domain'
          : 'Add Traefik labels to serve this app on a domain'}
      </label>
      {#if config.traefik.enabled}
        <div class="grid">
          <label>
            <span>Domain</span>
            <input type="text" bind:value={config.traefik.domain} pattern={patterns.domain}
              placeholder={domainPlaceholder} title="Domain the app will be served on"
              spellcheck="false" autocapitalize="off" autocomplete="off" />
          </label>
          <label>
            <span>App port</span>
            <input type="text" inputmode="numeric" bind:value={config.traefik.port} pattern={patterns.containerPort}
              required placeholder="80" title="Container port traffic is routed to" spellcheck="false" autocomplete="off" />
          </label>
          {#if traefikKind === 'labels'}
            <label>
              <span>Entrypoint</span>
              <input type="text" bind:value={config.traefik.entrypoint} pattern={patterns.ident}
                placeholder={config.traefik.tls ? 'websecure' : 'web'} title="Traefik entrypoint name"
                spellcheck="false" autocomplete="off" />
            </label>
            <label>
              <span>Backend scheme</span>
              <select bind:value={config.traefik.scheme} title="Protocol traefik uses to reach the app">
                <option value="">Auto</option>
                <option value="http">http</option>
                <option value="https">https</option>
              </select>
            </label>
          {/if}
          <label class="check boxed" title={traefikKind === 'ingress' ? 'Add a TLS block to the ingress' : 'Request a certificate via the resolver'}>
            <input type="checkbox" bind:checked={config.traefik.tls} /> TLS (HTTPS)
          </label>
          {#if config.traefik.tls}
            <label>
              <span>{traefikKind === 'ingress' ? 'Cert issuer' : 'Cert resolver'}</span>
              <input type="text" bind:value={config.traefik.certResolver} pattern={patterns.ident}
                placeholder={traefikKind === 'ingress' ? 'optional' : 'letsencrypt'}
                title={traefikKind === 'ingress'
                  ? 'cert-manager ClusterIssuer to provision the certificate, leave empty if you manage the TLS secret yourself'
                  : 'Traefik certificate resolver name'}
                spellcheck="false" autocomplete="off" />
            </label>
          {/if}
        </div>
      {/if}
    </fieldset>

    {#if fields.devices}
      <fieldset class="panel">
        <legend>Devices <HelpTip for="devices" /></legend>
        <div class="rows">
          {#each config.devices as dev, i (i)}
            <div class="row devices">
              <input type="text" bind:value={dev.host} pattern={patterns.devicePath} required={!!dev.container}
                placeholder="/dev/dri" aria-label="Host device" title="Host device to share with the container"
                spellcheck="false" autocomplete="off" />
              <span class="sep" aria-hidden="true">:</span>
              <input type="text" bind:value={dev.container} pattern={patterns.devicePath} placeholder="same as host"
                aria-label="Container device path" title="Path the device appears at inside the container"
                spellcheck="false" autocomplete="off" />
              <button type="button" class="remove" onclick={() => config.devices.splice(i, 1)}
                aria-label="Remove device {dev.host || i + 1}">&times;</button>
            </div>
          {/each}
          <button type="button" class="add" onclick={() => config.devices.push(emptyDevice())}>+ Add device</button>
        </div>
      </fieldset>
    {/if}
    <fieldset class="panel">
      <legend>Labels <HelpTip for="labels" /></legend>
      <div class="rows">
        {#each config.labels as label, i (i)}
          <div class="row labels">
            <input type="text" bind:value={label.name} pattern={patterns.envName} required={!!label.value}
              placeholder="traefik.enable" aria-label="Label name" spellcheck="false" autocomplete="off" />
            <span class="sep" aria-hidden="true">=</span>
            <input type="text" bind:value={label.value} placeholder="true" aria-label="Label value"
              spellcheck="false" autocomplete="off" />
            <button type="button" class="remove" onclick={() => config.labels.splice(i, 1)}
              aria-label="Remove label {label.name || i + 1}">&times;</button>
          </div>
        {/each}
        <button type="button" class="add" onclick={() => config.labels.push(emptyLabel())}>+ Add label</button>
      </div>
    </fieldset>
  {/if}
</div>

<style lang="scss">
  .config-form {
    --invalid: #e5534b;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    .panel {
      display: block;
      margin: 0;
      padding: 0.75rem;
      border: none;
      border-radius: 6px;
      background: var(--card-2);
      legend {
        float: left;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
        width: 100%;
        padding: 0;
        margin: 0 0 0.6rem;
        font-size: 0.7rem;
        font-weight: 500;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: color-mix(in srgb, var(--foreground) 60%, transparent);
      }
      .grid,
      .rows {
        clear: both;
      }
      > .check {
        clear: both;
        &:not(:last-child) {
          margin-bottom: 0.75rem;
        }
      }
      .rows + .check {
        margin-top: 0.75rem;
      }
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(min(13rem, 100%), 1fr));
      gap: 0.75rem;
      align-items: end;
    }
    .rows {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
    label:not(.check) {
      display: flex;
      flex-direction: column;
      gap: 0.3rem;
      font-size: 0.85rem;
      > span:first-child {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
        color: color-mix(in srgb, var(--foreground) 80%, transparent);
      }
    }
    .row {
      display: grid;
      gap: 0.4rem;
      align-items: center;
      &.ports { grid-template-columns: minmax(6rem, 1fr) auto minmax(5rem, 1fr) auto auto; }
      &.env { grid-template-columns: minmax(8rem, 1fr) minmax(8rem, 2fr) auto; }
      &.volumes { grid-template-columns: minmax(7rem, 1.2fr) auto minmax(7rem, 1fr) auto auto; }
      &.labels, &.devices { grid-template-columns: minmax(7rem, 1fr) auto minmax(7rem, 1fr) auto; }
      .sep {
        opacity: 0.5;
      }
      .key {
        font-size: 0.9rem;
        display: flex;
        flex-direction: column;
        overflow-wrap: anywhere;
        .name {
          display: flex;
          align-items: center;
          gap: 0.3rem;
        }
        code {
          font-size: 0.7rem;
          opacity: 0.6;
        }
      }
    }
    input:not([type='checkbox']),
    select {
      min-width: 0;
      padding: 0.4rem 0.5rem;
      border-radius: 6px;
      border: 1px solid transparent;
      background: var(--background);
      color: var(--foreground);
      font: inherit;
      font-size: 0.95rem;
      &:focus-visible {
        outline: 2px solid var(--accent);
        outline-offset: -1px;
      }
      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
    }
    input:user-invalid {
      border-color: var(--invalid);
      &:focus-visible {
        outline-color: var(--invalid);
      }
    }
    .check {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-size: 0.9rem;
      cursor: pointer;
      input {
        width: 1rem;
        height: 1rem;
        margin: 0;
        accent-color: var(--accent);
        flex-shrink: 0;
      }
      &.boxed {
        padding: 0.4rem 0.5rem;
        border-radius: 6px;
        background: var(--background);
      }
    }
    .remove {
      padding: 0.2rem 0.5rem;
      background: var(--background);
      border: none;
      border-radius: 6px;
      color: var(--foreground);
      font: inherit;
      cursor: pointer;
      &:hover {
        color: var(--invalid);
      }
      &:focus-visible {
        outline: 2px solid var(--accent);
      }
    }
    .add {
      align-self: start;
      padding: 0;
      background: none;
      border: none;
      color: var(--accent);
      font: inherit;
      font-size: 0.85rem;
      cursor: pointer;
      &:hover {
        text-decoration: underline;
      }
      &:focus-visible {
        outline: 2px solid var(--accent);
        outline-offset: 2px;
      }
    }
    .advanced-toggle {
      align-self: start;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.4rem 0.75rem;
      background: var(--card-2);
      border: none;
      border-radius: 6px;
      color: var(--foreground);
      font: inherit;
      font-size: 0.85rem;
      cursor: pointer;
      transition: all 0.2s ease-in-out;
      .caret {
        transition: transform 0.2s ease-in-out;
        &.open {
          transform: rotate(90deg);
        }
      }
      &:hover {
        color: var(--accent);
        box-shadow: var(--shadow);
      }
      &:focus-visible {
        outline: 2px solid var(--accent);
        outline-offset: 2px;
      }
    }
    @media (prefers-reduced-motion: reduce) {
      .advanced-toggle,
      .advanced-toggle .caret {
        transition: none;
      }
    }
    @media (max-width: 600px) {
      .row.ports, .row.volumes { grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) auto auto; }
      .row.labels, .row.devices { grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) auto; }
      .row.env {
        grid-template-columns: 1fr auto;
        .key, > input[aria-label='Variable name'] {
          grid-column: 1 / -1;
        }
      }
    }
  }
</style>
