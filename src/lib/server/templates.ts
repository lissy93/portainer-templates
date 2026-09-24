import yaml from 'js-yaml';
import { error } from '@sveltejs/kit';
import { get } from 'svelte/store';
import { templates } from '$src/store';
import { templatesUrl } from '$src/constants';
import type { Build, DependsOn, Environment, Service, Template, Volume } from '$src/Types';

type Fetch = typeof globalThis.fetch;

/* Fetch the full templates list, reusing the copy already in the store */
export async function loadTemplates(fetch: Fetch): Promise<Template[]> {
  const cachedList = get(templates);
  if (cachedList?.length) return cachedList;
  try {
    const data = await fetch(templatesUrl).then((res) => res.json());
    templates.set(data.templates);
    return data.templates;
  } catch {
    throw error(503, 'Could not load the templates list. Please try again shortly.');
  }
}

/* Merge stackfile env values over the template's richer defs (labels, selects), keeping both */
export const mergeEnv = (defs: Environment[] = [], values: Environment[] = []): Environment[] => {
  if (!values.length) return defs;
  const byName = new Map(defs.map((env) => [env.name, env]));
  const seen = new Set(values.map((env) => env.name));
  return [
    ...values.map((env) => ({ ...byName.get(env.name), ...env })),
    ...defs.filter((env) => !seen.has(env.name)),
  ];
};

/* Compose environment can be a map ({ KEY: value }) or a list ([ "KEY=value" ]) */
const parseEnv = (environment?: Record<string, unknown> | string[]): Environment[] => {
  if (!environment) return [];
  if (Array.isArray(environment)) {
    return environment.map((entry) => {
      const [name, ...rest] = String(entry).split('=');
      return { name, value: rest.join('=') };
    });
  }
  return Object.entries(environment).map(([name, value]) => ({
    name,
    value: value == null ? '' : String(value),
  }));
};

/* Compose volumes are strings ("source:target"); skip long-syntax objects we can't render inline */
const parseVolumes = (volumes?: unknown[]): Volume[] =>
  (volumes || [])
    .filter((vol): vol is string => typeof vol === 'string')
    .map((vol) => {
      const [source, target] = vol.split(':');
      return target ? { bind: source, container: target } : { container: source };
    });

type ComposeServiceRaw = {
  image?: string;
  entrypoint?: string;
  command?: string;
  ports?: string[];
  build?: Build;
  interactive?: boolean;
  volumes?: unknown[];
  restart?: Service['restart_policy'];
  environment?: Record<string, unknown> | string[];
  user?: string | number;
  devices?: unknown[];
  depends_on?: DependsOn;
  healthcheck?: Record<string, unknown>;
};

/* Fetch and parse the template's stackfile, keeping the raw text too */
export const getServices = async (template: Template, fetch: Fetch): Promise<{ services: Service[]; stackfile: string | null }> => {
  try {
    if (!template?.repository) return { services: [], stackfile: null };
    const { url: repoUrl, stackfile } = template.repository;
    const path = `${repoUrl.replace('github.com', 'raw.githubusercontent.com')}/HEAD/${stackfile}`;
    const response = await fetch(path);
    if (!response.ok) return { services: [], stackfile: null };
    const data = await response.text();
    const parsedData = yaml.load(data) as { services?: Record<string, ComposeServiceRaw> } | null;
    if (!parsedData?.services) return { services: [], stackfile: null };

    const services = Object.entries(parsedData.services).map(([name, serviceData]) => ({
      name,
      image: serviceData.image,
      entrypoint: serviceData.entrypoint,
      command: serviceData.command,
      ports: serviceData.ports,
      build: serviceData.build,
      interactive: serviceData.interactive,
      volumes: parseVolumes(serviceData.volumes),
      restart_policy: serviceData.restart,
      env: parseEnv(serviceData.environment),
      user: serviceData.user != null ? String(serviceData.user) : undefined,
      devices: (serviceData.devices ?? []).filter((dev): dev is string => typeof dev === 'string'),
      depends_on: serviceData.depends_on,
      healthcheck: serviceData.healthcheck,
    }));
    return { services, stackfile: data };
  } catch (error) {
    console.error('Error fetching or parsing YAML:', error);
    return { services: [], stackfile: null };
  }
};
