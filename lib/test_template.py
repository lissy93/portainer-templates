"""Tests templates the way Portainer deploys them, then checks they run"""
import argparse
import base64
import copy
import csv
import html
import itertools
import json
import os
import re
import secrets
import shlex
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from typing import NamedTuple
from urllib.parse import urlparse

import requests

import sources_list
from combine import TYPE_LABELS, normalize_string, normalize_template
from log import get_logger, banner
from portainer import Portainer, PortainerError
from validate_sources import check_templates

log = get_logger()

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
LOCAL_DIR = os.path.join(ROOT, 'sources', 'local')
REPO = os.environ.get('GITHUB_REPOSITORY', 'lissy93/portainer-templates')
GUIDE = f'https://github.com/{REPO}/blob/main/.github/CREATING_A_TEMPLATE.md'
SETTLE = 15  # seconds an app has to keep answering to count as up
LOG_LINES = 50
TEST_IDS = itertools.count(1)  # keeps names unique if a title repeats
PROBE_IMAGE = 'busybox:1.37'  # used to see which ports an app listens on
IGNORED_FIELDS = ('network', 'hostname', 'labels')  # Portainer's form drops these

SECRET_HINT = re.compile(r'pass|secret|key|token|salt|required', re.IGNORECASE)
OPENSSL_HINT = re.compile(r'openssl rand -(hex|base64) (\d+)')
PINNED_REF = re.compile(r'^(?:[0-9a-f]{40}|v?\d+(?:\.\d+)+)$')
TYPE_SUFFIX = re.compile(rf'\s*\((?:{"|".join(TYPE_LABELS.values())})\)$')
RATE_LIMITED = re.compile(r'toomanyrequests|429 Too Many Requests', re.IGNORECASE)
COMPOSE_WARNING = re.compile(r'level=warning msg="((?:[^"\\]|\\.)*)"')
UNSET_VARIABLE = re.compile(r'^The "(\w+)" variable is not set')

class Case(NamedTuple):
    """One template to test, where it came from, or why it can't be"""
    title: str
    where: str
    template: dict | None = None
    problem: str | None = None
    source: sources_list.Source | None = None
    target: str | None = None  # what to pass this script to re-run the test

class Result:
    """What testing one template found, logged as it goes"""
    def __init__(self, case):
        self.title, self.where, self.target = case.title, case.where, case.target
        self.errors, self.warnings, self.outcome = [], [], 'not started'
        self.logs, self.status, self.culprit = '', [], None
        self.annotate = locate(case)

    def error(self, message):
        log.error(f'{self.title}: {message}', extra={'annotate': self.annotate})
        self.errors.append(message)

    def warn(self, message):
        log.warning(f'{self.title}: {message}', extra={'annotate': self.annotate})
        self.warnings.append(message)

    @property
    def icon(self):
        return '❌' if self.errors else '⚠️' if self.warnings else '✅'

def run(*command, timeout=600, **kwargs):
    """Runs a command and returns its output, raising with its stderr if it fails"""
    return subprocess.run(command, check=True, text=True, capture_output=True,
                          timeout=timeout, **kwargs).stdout

def rate_limited(err):
    """Whether a command failed because the registry is rate limiting us"""
    return isinstance(err, subprocess.CalledProcessError) \
        and bool(RATE_LIMITED.search(err.stderr or ''))

def reason(err):
    """The last line a failed command printed, which is usually the useful one"""
    if isinstance(err, subprocess.TimeoutExpired):
        return f'timed out after {err.timeout}s'
    if isinstance(err, ValueError):
        return str(err)
    if rate_limited(err):
        return 'the registry\'s pull rate limit was hit, which says nothing about the ' \
               'template, so re-run the check later'
    lines = [line for line in (err.stderr or err.stdout or '').strip().splitlines()
             if line.strip() and not line.startswith("Run 'docker")]  # docker's --help hint
    return lines[-1] if lines else f'exit code {err.returncode}'

@contextmanager
def section(title):
    """Folds each template's output into its own group in the Actions log"""
    ci = os.environ.get('GITHUB_ACTIONS')
    sys.stderr.write(f'::group::{title}\n' if ci else f'\n▶ {title}\n')
    try:
        yield
    finally:
        if ci:
            sys.stderr.write('::endgroup::\n')

def title_key(title):
    """A title as combine.py compares them, minus any (container) or (stack) suffix"""
    return normalize_string(TYPE_SUFFIX.sub('', title))

def load_json(path):
    with open(path) as file:
        return json.load(file)

def local_files():
    return sorted(f for f in os.listdir(LOCAL_DIR) if f.endswith('.json'))

def local_templates():
    """Each readable file in sources/local/, with its templates"""
    for name in local_files():
        try:
            yield name, load_json(os.path.join(LOCAL_DIR, name))['templates']
        except (ValueError, KeyError, TypeError):
            continue  # validate_sources.py reports a broken file

def git_show(ref, path):
    """A file's content at a git ref, or None if it didn't exist there"""
    try:
        return run('git', '-C', ROOT, 'show', f'{ref}:{path}')
    except subprocess.CalledProcessError:
        return None

def locate(case):
    """Where a case lives, so CI can flag its problems on that line of the PR"""
    path, _, line = case.where.partition(':')
    if path == 'sources.csv' and line:
        return {'file': path, 'line': line}
    if not path.startswith('sources/local/'):
        return {}
    needle = f'"title": {json.dumps(case.title, ensure_ascii=False)}'
    with open(os.path.join(ROOT, path)) as file:
        line = next((n for n, text in enumerate(file, start=1) if needle in text), None)
    return {'file': path, 'line': line} if line else {'file': path}

# --- Working out what to test ---

def source_cases(source, where):
    """The template an app source publishes, fetched like download.py does"""
    def broken(problem):
        return [Case(source.name, where, problem=problem, target=source.name)]

    try:
        payload, error = (load_json(source.url), None) if os.path.isfile(source.url) \
            else sources_list.fetch_json(source.url)
    except ValueError as err:
        payload, error = None, err
    if error:
        return broken(f'could not fetch valid JSON ({error})')
    templates = [t for t in sources_list.templates_in(payload, allow_bare=True) or []
                 if isinstance(t, dict)]
    if not templates:
        return broken('found no templates, so the build would skip it')
    if len(templates) > sources_list.MAX_APP_TEMPLATES:
        return broken(f'holds {len(templates)} templates, but an app source may publish '
                      f'{sources_list.MAX_APP_TEMPLATES}, so the build would skip it')
    return [Case(str(t.get('title', source.name)), where, t, source=source, target=source.name)
            for t in templates]

def csv_lines():
    """Source name -> its line in sources.csv, for pointing at the row"""
    return {cells[0]: line for line, cells in sources_list.rows()}

def changed_sources(ref):
    """App sources added to sources.csv, or pointed somewhere new, since ref"""
    old = git_show(ref, 'sources.csv') or ''
    before = {sources_list.parse(cells)._replace(maintainer='') for cells in
              ([c.strip() for c in row] for row in csv.reader(old.splitlines()) if any(row))
              if not sources_list.row_problems(cells)}
    lines, cases = csv_lines(), []
    for source in sources_list.load():
        if source._replace(maintainer='') in before:
            continue
        if source.is_app:
            cases += source_cases(source, f'sources.csv:{lines[source.name]}')
        else:
            log.info(f'Skipping {source.name}: only app sources get started, not collections')
    return cases

def changed_local(ref):
    """Local templates that are new or changed since ref, or whose stack file is"""
    changed = set(run('git', '-C', ROOT, 'diff', '--name-only', ref).split())
    cases = []
    for name in local_files():
        path = f'sources/local/{name}'
        try:
            templates = load_json(os.path.join(ROOT, path))['templates']
            old = json.loads(git_show(ref, path) or '{"templates": []}')['templates']
        except (ValueError, KeyError, TypeError) as err:
            cases.append(Case(name, path, problem=f'could not read its templates ({err})'))
            continue
        before = {json.dumps(t, sort_keys=True) for t in old}
        cases += [Case(str(t.get('title', name)), path, t, target=str(t.get('title', name)))
                  for t in templates if isinstance(t, dict)
                  and (json.dumps(t, sort_keys=True) not in before
                       or (t.get('repository') or {}).get('stackfile') in changed)]
    return cases

def titled(templates, where):
    """Cases for each template, keyed by title the ways combine.py compares them"""
    found = {}
    for t in templates:
        if isinstance(t, dict) and isinstance(t.get('title'), str):
            for key in {normalize_string(t['title']), title_key(t['title'])}:
                found.setdefault(key, []).append(Case(t['title'], where, t, target=t['title']))
    return found

def target_cases(targets):
    """Cases for each source name, url, file or title, or every app source if none"""
    sources, lines = {s.name: s for s in sources_list.load()}, csv_lines()
    if not targets:
        return [case for s in sources.values() if s.is_app
                for case in source_cases(s, f'sources.csv:{lines[s.name]}')]
    local = {}
    for name, templates in local_templates():
        for key, found in titled(templates, f'sources/local/{name}').items():
            local.setdefault(key, []).extend(found)
    published = load_json(os.path.join(ROOT, 'templates.json'))['templates']
    published = titled(published, 'templates.json')
    cases = []
    for target in targets:
        if target.startswith(('http://', 'https://')) or os.path.isfile(target):
            cases += source_cases(sources_list.Source(target, target, '', sources_list.APP), target)
        elif target in sources and sources[target].is_app:
            cases += source_cases(sources[target], f'sources.csv:{lines[target]}')
        elif target in sources:
            cases.append(Case(target, f'sources.csv:{lines[target]}', problem='is a collection, '
                              'so name the template you want from it by its title instead'))
        elif normalize_string(target) in local:
            cases += local[normalize_string(target)]
        elif normalize_string(target) in published:
            cases += published[normalize_string(target)]
        else:
            cases.append(Case(target, 'input', problem='matches no source, url, file or title'))
    return cases

# --- Checks before starting anything ---

def check_fields(result, raw):
    """Runs the same schema checks as validate_sources.py"""
    errors, warnings = check_templates('', [raw])
    if not errors:
        log.info('✓ Fields match the schema')
    for message in errors:
        result.error(message.split('": ', 1)[-1])
    for message in warnings:
        result.warn(message.split('": ', 1)[-1])

def check_source(result, template, source):
    """Things only an app source gets wrong: a pinned url, or a copy that beats it"""
    parts = urlparse(source.url).path.split('/')
    if urlparse(source.url).hostname == 'raw.githubusercontent.com' and len(parts) > 3 \
       and PINNED_REF.match(parts[3]):
        result.warn(f'url is pinned to {parts[3]}, so later changes to the template won\'t '
                    'flow through. Point it at a branch instead')
    if not source.maintainer or not isinstance(template.get('title'), str):
        return
    key = (title_key(template['title']), template['type'])
    for name, local in local_templates():
        titles = {(title_key(str(t.get('title', ''))), t.get('type', 1))
                  for t in local if isinstance(t, dict)}
        if key in titles:
            result.error(f'sources/local/{name} has its own copy of {template["title"]}, which '
                         'beats every external source, so remove it from there')
    for other in load_json(os.path.join(ROOT, 'templates.json'))['templates']:
        if (title_key(other['title']), other['type']) == key \
           and other.get('maintainer') != source.maintainer:
            result.warn(f'replaces the published {other["title"]} from '
                        f'{other.get("maintainer") or "another source"}, as app sources win')

def check_logo(result, url):
    """The logo has to load as an image, or the app shows up with a broken one"""
    if not url:
        return
    try:
        with requests.get(url, timeout=30, stream=True) as response:
            response.raise_for_status()
            kind = response.headers.get('Content-Type', '')
    except requests.RequestException as err:
        return result.warn(f'logo failed to load ({err})')
    if not kind.startswith('image/'):
        return result.warn(f'logo is served as {kind or "an unknown type"}, not an image')
    log.info('✓ Logo loads')

def check_image(result, image):
    """The image needs an amd64 build, and ideally arm64 too, for Pis"""
    inspect = ['docker', 'buildx', 'imagetools', 'inspect', '--format']
    try:
        # Just the index, as registries count every manifest fetched as a pull
        index = json.loads(run(*inspect, '{{json .Manifest}}', image, timeout=120))
        if 'manifests' in index:
            platforms = [m.get('platform') or {} for m in index['manifests']]
        else:  # a single-arch image only names its arch in its config
            platforms = [json.loads(run(*inspect, '{{json .Image}}', image, timeout=120))]
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
        verb = 'checked' if rate_limited(err) else 'found'
        return result.error(f'image {image} can\'t be {verb} ({reason(err)})')
    arches = sorted({p.get('architecture') for p in platforms if p.get('os') == 'linux'})
    log.info(f'✓ Found {image}, built for {", ".join(arches) or "nothing on linux"}')
    if 'amd64' not in arches:
        result.error(f'image {image} has no amd64 build, only {", ".join(arches) or "none"}')
    elif 'arm64' not in arches:
        result.warn(f'image {image} has no arm64 build, so it won\'t run on ARM hosts')

def check_ports(result, template):
    """Portainer reads ports as [host:]container/protocol, and misreads anything else"""
    for port in template.get('ports', []):
        mapping, _, protocol = port.partition('/')
        if mapping.count(':') > 1:
            fixed = ':'.join(mapping.split(':')[-2:])
            result.error(f'port {port} has a host IP, which Portainer reads as the host port, so '
                         f'it can\'t deploy. Use {fixed}/{protocol or "tcp"} instead')
        elif protocol not in ('tcp', 'udp'):
            result.error(f'port {port} needs /tcp or /udp on the end. Without it Portainer asks '
                         f'Docker for {mapping.rpartition(":")[2]}/undefined, and the container '
                         'fails to start with "unknown protocol"')

def check_ignored_fields(result, template):
    """Fields Portainer drops from container templates, so they never apply"""
    ignored = [f'"{key}"' for key in IGNORED_FIELDS if template.get(key)]
    if ignored:
        result.warn(f'Portainer ignores {" and ".join(ignored)} on container templates, so '
                    'people deploying this won\'t get them. Mention any that matter in the note')

def check_volumes(result, template):
    """Every VOLUME in the image's Dockerfile needs a volume in the template"""
    mapped = {v['container'].rstrip('/') for v in template.get('volumes', [])}
    # Runs once the image is pulled, so it costs the registry nothing
    volumes = json.loads(run('docker', 'image', 'inspect', '--format', '{{json .Config.Volumes}}',
                             template['image'])) or {}
    for path in sorted(volumes):
        if path.rstrip('/') not in mapped:
            result.warn(f'the image keeps data in {path}, but the template has no volume '
                        'for it, so that data is easily lost when the container is recreated')

# --- The deploy form ---

def form_value(var):
    """What Portainer's form starts a field at, or a stand-in for a blank secret"""
    if var.get('select'):
        return next((o['value'] for o in var['select'] if o.get('default')), '')
    if var.get('default'):
        return var['default']
    if var['name'].endswith('_URL'):
        return 'http://localhost'
    text = ' '.join(str(var.get(key, '')) for key in ('name', 'label', 'description'))
    if not SECRET_HINT.search(text):
        return ''
    hint = OPENSSL_HINT.search(text)
    size = int(hint[2]) if hint else 16
    return base64.b64encode(secrets.token_bytes(size)).decode() \
        if hint and hint[1] == 'base64' else secrets.token_hex(size)

def form_values(template):
    return {var['name']: form_value(var) for var in template.get('env', [])}

# --- Reading a stack's compose file ---

def in_this_repo(repository):
    """Whether the stack's compose file lives in this repo"""
    url = repository['url'].rstrip('/').removesuffix('.git').lower()
    return url.endswith(f'github.com/{REPO.lower()}')

def compose_env():
    """Just what docker needs, as Portainer doesn't pass its own env to stacks"""
    return {k: v for k, v in os.environ.items() if k in ('PATH', 'HOME') or k.startswith('DOCKER_')}

def compose_warnings(stderr, checkout):
    """Compose's warnings about the stack, reworded where they're cryptic"""
    for found in COMPOSE_WARNING.finditer(stderr):
        message = found[1].replace('\\"', '"').replace(os.path.join(checkout, ''), '')
        unset = UNSET_VARIABLE.match(message)
        yield (f'the compose file uses ${{{unset[1]}}} with no default, and the template has '
               f'no "{unset[1]}" field, so it\'s always blank') if unset \
            else f'docker compose: {message}'

def check_variables(result, template, compose, stackfile):
    """Every form field should be used by the stack, or what people type is lost"""
    with open(stackfile) as file:
        if 'stack.env' in file.read():
            return  # the whole form reaches the app through env_file
    try:
        used = json.loads(run(*compose, 'config', '--variables', '--format', 'json',
                              env=compose_env()))
    except (subprocess.CalledProcessError, ValueError):
        return  # compose before 2.23 can't list them
    for name in (var['name'] for var in template.get('env', [])):
        if name not in used and not name.startswith('COMPOSE_'):
            result.warn(f'"{name}" is on the deploy form, but the compose file never uses '
                        f'${{{name}}}, so whatever people enter there is ignored')

def check_mounts(result, config, checkout):
    """Relative mounts point inside Portainer's container, not at the repo"""
    for name, svc in config['services'].items():
        for volume in svc.get('volumes', []):
            source = volume.get('source') or ''
            if volume.get('type') == 'bind' and source.startswith(os.path.join(checkout, '')):
                result.warn(f'{name} mounts {os.path.relpath(source, checkout)} from the repo, '
                            'but Portainer runs compose inside its own container, so on the host '
                            'that path is an empty folder rather than the repo\'s files')

def load_stack(result, template, workdir):
    """Clones and resolves a stack like Portainer will, and returns its images"""
    repo = template['repository']
    local = in_this_repo(repo)
    checkout = os.path.realpath(ROOT if local else os.path.join(workdir, 'repo'))
    if not local:
        run('git', 'clone', '--quiet', '--depth', '1', repo['url'], checkout,
            env=os.environ | {'GIT_TERMINAL_PROMPT': '0'})
    stackfile = os.path.join(checkout, repo['stackfile'])
    if not os.path.isfile(stackfile):
        raise ValueError(f'{repo["stackfile"]} isn\'t in {repo["url"]} on its default branch, '
                         'which is the only branch Portainer reads')
    compose = ['docker', 'compose', '--file', stackfile]
    values = form_values(template)
    if values:
        # Like Portainer, put the form in stack.env, after any .env beside the stack
        dotenv, defaults = os.path.join(os.path.dirname(stackfile), '.env'), ''
        if os.path.isfile(dotenv):
            with open(dotenv) as file:
                defaults = file.read()
        env_file = os.path.join(workdir if local else checkout, 'stack.env')
        with open(env_file, 'w') as file:
            file.write(defaults + '\n' + ''.join(f'{k}={v}\n' for k, v in values.items()))
        compose += ['--env-file', env_file]
    resolved = subprocess.run([*compose, 'config', '--format', 'json'], text=True,
                              capture_output=True, timeout=120, env=compose_env())
    if resolved.returncode:
        raise subprocess.CalledProcessError(resolved.returncode, compose,
                                            resolved.stdout, resolved.stderr)
    for message in compose_warnings(resolved.stderr, checkout):
        result.warn(message)
    check_variables(result, template, compose, stackfile)
    config = json.loads(resolved.stdout)
    check_mounts(result, config, checkout)
    return list(dict.fromkeys(s['image'] for s in config['services'].values() if s.get('image')))

def local_stack(repository):
    """This repo's own copy of a stack file, so a PR's version is what deploys"""
    if not in_this_repo(repository):
        return None
    with open(os.path.join(ROOT, repository['stackfile'])) as file:
        return file.read()

# --- Watching it run ---

def containers(selector):
    ids = run('docker', 'ps', '--all', '--quiet', '--filter', selector).split()
    return json.loads(run('docker', 'inspect', *ids)) if ids else []

def service(c):
    """A stack's service name for the container, or None if it isn't part of one"""
    return (c['Config']['Labels'] or {}).get('com.docker.compose.service')

def who(c):
    return service(c) or 'the container'

def health(c):
    return (c['State'].get('Health') or {}).get('Status')

def health_output(c):
    """The last line the health check printed, which usually says why it failed"""
    checks = (c['State'].get('Health') or {}).get('Log') or []
    lines = (checks[-1].get('Output') or '').strip().splitlines() if checks else []
    return f' ({lines[-1][:200]})' if lines else ''

def describe(c):
    """One line on a container's state, for the report"""
    state = c['State']
    details = [state['Status']]
    if state['Status'] == 'exited':
        details.append(f'exit code {state["ExitCode"]}')
    if c['RestartCount']:
        details.append(f'{c["RestartCount"]} restarts')
    if health(c):
        details.append(health(c))
    return f'{service(c) or "container"}: {", ".join(details)}'

def published(c):
    """Container port -> the local port it's published on, like '80/tcp' -> '32768'"""
    if c['HostConfig']['NetworkMode'] == 'host':
        return {port: port.split('/')[0] for port in c['Config'].get('ExposedPorts') or {}}
    ports = c['NetworkSettings']['Ports'] or {}
    return {port: bindings[0]['HostPort'] for port, bindings in ports.items() if bindings}

def http_status(port):
    """The HTTP status a local port answers with, or None"""
    try:
        response = requests.get(f'http://127.0.0.1:{port}/', timeout=5, allow_redirects=False)
        return response.status_code
    except requests.RequestException:
        return None

def listening(c):
    """Ports the container listens on, as '80/tcp' -> whether only on localhost"""
    if c['HostConfig']['NetworkMode'] == 'host':
        return None  # it shares the host's network, so there's nothing of its own to read
    try:
        out = run('docker', 'run', '--rm', '--network', f'container:{c["Id"]}', PROBE_IMAGE,
                  'netstat', '-lntu', timeout=30)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    found = {}
    for cells in (line.split() for line in out.splitlines()):
        if len(cells) > 3 and cells[0].startswith(('tcp', 'udp')):
            host, _, port = cells[3].rpartition(':')
            local = host.startswith(('127.', '::ffff:127.')) or host == '::1'
            key = f'{port}/{cells[0][:3]}'
            found[key] = found.get(key, True) and local
    return found

def probe(running):
    """How the app answers, else what's wrong and whether that's an error"""
    exposed = [(c, published(c)) for c in running if published(c)]
    if not exposed:
        return 'running, with no ports to check', None, False
    failing = {}
    for c, ports in exposed:
        for port, host in ports.items():
            status = http_status(host) if port.endswith('/tcp') else None
            if status and status < 500:
                return f'answered HTTP {status} on {port}', None, False
            if status:
                failing[port] = status
    if failing:
        errors = ', '.join(f'HTTP {status} on {port}' for port, status in failing.items())
        return None, f'it only answers with {errors}', False
    # No HTTP, so look at what's listening behind each published port
    clues = []
    for c, ports in exposed:
        found = listening(c)
        if found is None:
            continue
        name, wanted = service(c) or 'the app', ', '.join(sorted(ports))
        reachable = sorted(port for port in ports if found.get(port) is False)
        if reachable:
            return f'listening on {", ".join(reachable)} (not HTTP)', None, False
        local = sorted(port for port in ports if found.get(port))
        others = sorted(port for port, loopback in found.items()
                        if not loopback and port not in ports)
        if local:
            clues.append(f'{name} only listens on {", ".join(local)} at 127.0.0.1 inside '
                         'its container, so nothing outside can reach it. It needs 0.0.0.0')
        elif others:
            clues.append(f'{name} listens on {", ".join(others)}, but the template publishes '
                         f'{wanted}, so the container side of the port mapping is probably wrong')
        else:
            clues.append(f'nothing in {name} listens on {wanted}')
    if clues:
        return None, '; '.join(clues), True
    everything = ', '.join(sorted(port for _, ports in exposed for port in ports))
    problem = f'nothing answered over HTTP on {everything}. Fine if it doesn\'t speak HTTP'
    return None, problem, False

def watch(result, selector, timeout, again=''):
    """Waits for it to answer and stay up, failing on crashes or bad health checks"""
    def fail(message, c=None):
        result.outcome = f'{again}, {message}' if again else message
        result.culprit = c and service(c)
        result.error(result.outcome)

    started, since = time.monotonic(), None
    while True:
        found, waited = containers(selector), int(time.monotonic() - started)
        for c in found:
            state = c['State']
            if c['RestartCount'] >= 3:
                return fail(f'{who(c)} keeps restarting (exit code {state["ExitCode"]})', c)
            if state['Status'] == 'exited' and state['ExitCode']:
                return fail(f'{who(c)} exited with code {state["ExitCode"]} after {waited}s', c)
            if health(c) == 'unhealthy':
                return fail(f'{who(c)} failed its health check{health_output(c)}', c)
        restarting = [c for c in found if c['State']['Restarting']]
        running = [c for c in found if c['State']['Running'] and not c['State']['Restarting']]
        if not running and not restarting:
            return fail(f'nothing was left running after {waited}s')
        waiting = [c for c in running if health(c) == 'starting']
        ready, problem, serious = (None, None, False) if restarting or waiting else probe(running)
        since = (waited if since is None else since) if ready else None
        if ready and waited - since >= SETTLE:
            result.outcome = f'{ready} after {since}s'
            log.info(f'✓ {result.outcome}' + (f' ({again})' if again else ''))
            return True
        if waited >= timeout and not ready:
            if waiting:
                c = waiting[0]
                return fail(f'{who(c)} never passed its health check within {timeout}s'
                            f'{health_output(c)}', c)
            if restarting:
                return fail(f'{who(restarting[0])} was still restarting after {timeout}s',
                            restarting[0])
            if serious:
                return fail(f'{problem} (waited {timeout}s)')
            result.outcome = f'{again + ", " if again else ""}running, but {problem}'
            return result.warn(result.outcome)
        time.sleep(5)

def tail_logs(found, culprit):
    """Recent logs from the failing service, or from everything if it's unclear"""
    picked = [c for c in found if service(c) == culprit] if culprit else found
    logs = []
    for c in picked:
        text = subprocess.run(['docker', 'logs', '--tail', str(LOG_LINES), c['Id']], text=True,
                              check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
        prefix = f'{service(c) or "container"} | ' if len(picked) > 1 else ''
        logs += [f'{prefix}{line}\n' for line in text.splitlines()]
    return ''.join(logs)

def remove(selector):
    """Deletes everything a test made, and in CI its images too, to save disk"""
    def quietly(*command):
        subprocess.run(['docker', *command], capture_output=True, check=False)

    found = containers(selector)
    if found:
        quietly('rm', '--force', '--volumes', *(c['Id'] for c in found))
    if selector.startswith('label='):
        for kind in ('volume', 'network'):
            ids = run('docker', kind, 'ls', '--quiet', '--filter', selector).split()
            if ids:
                quietly(kind, 'rm', *ids)
    images = {c['Config']['Image'] for c in found}
    if images and os.environ.get('CI'):  # locally, they may be someone's own images
        quietly('rmi', *images)

# --- Starting it ---

def start_container(template, name):
    """docker run, the way Portainer's form builds a container template"""
    args = ['docker', 'run', '--detach', '--name', name]
    for port in template.get('ports', []):
        args += ['--publish', f'127.0.0.1::{port.rpartition(":")[2]}']
    for volume in template.get('volumes', []):
        mount = f'{volume["bind"]}:{volume["container"]}' if volume.get('bind') \
            else volume['container']
        args += ['--volume', mount + (':ro' if volume.get('readonly') else '')]
    for key, value in form_values(template).items():
        args += ['--env', f'{key}={value}']
    args += ['--restart', template.get('restart_policy') or 'always']  # Portainer's default
    if template.get('privileged'):
        args.append('--privileged')
    if template.get('interactive'):
        args += ['--interactive', '--tty']
    run(*args, template['image'], *shlex.split(template.get('command') or ''))

def deploy(result, template, timeout, portainer):
    """Starts it with the form untouched, then restarts it, watching both times"""
    slug = re.sub(r'[^a-z0-9]+', '-', result.title.lower()).strip('-')
    name = f'test-{slug}-{os.getpid()}-{next(TEST_IDS)}'
    stack = template['type'] == 3
    selector = f'label=com.docker.compose.project={name}' if stack else f'name=^{name}$'
    again = 'after a stop and start in Portainer' if stack else 'after a restart'
    up, stack_id = False, None
    try:
        if stack:
            log.info('Deploying the stack through Portainer')
            repo = template['repository']
            stack_id = portainer.deploy(name, form_values(template), repo, local_stack(repo))
        else:
            log.info(f'Starting {template["image"]}')
            start_container(template, name)
            check_volumes(result, template)
        up = watch(result, selector, timeout)
        if up:
            first = result.outcome
            log.info(f'Checking it comes back {again}, with the data from its first start')
            if stack:
                portainer.restart(stack_id)
            else:
                run('docker', 'restart', name)
            up = watch(result, selector, timeout, again)
            if up:
                result.outcome = f'{first}, and again {again}'
    except PortainerError as err:
        result.outcome = 'Portainer couldn\'t deploy it'
        result.error(f'{result.outcome} ({err})')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
        result.outcome = 'failed to start'
        result.error(f'failed to start ({reason(err)})')
    finally:
        found = [] if up else containers(selector)
        if found:
            result.status = [describe(c) for c in found]
            result.logs = tail_logs(found, result.culprit)
            log.info('State: ' + '; '.join(result.status))
            log.info(f'Last lines of its logs:\n{result.logs}')
        remove(selector)

# --- Testing one template ---

def test(case, start, timeout, portainer):
    """Tests one template, turning any crash into a failure instead of stopping"""
    result = Result(case)
    with section(f'{case.title} ({case.where})'):
        try:
            check(result, case, start, timeout, portainer)
        except Exception as err:
            result.outcome = 'test crashed'
            result.error(f'test crashed ({type(err).__name__}: {err})')
    return result

def check(result, case, start, timeout, portainer):
    """Runs every check on one template, and starts it if they all pass"""
    if case.problem:
        result.outcome = case.problem
        return result.error(case.problem)
    template = copy.deepcopy(case.template)
    try:
        normalize_template(template)
    except Exception as err:
        return result.error(f'failed to normalize ({err})')
    log.info(f'Type: {TYPE_LABELS.get(template["type"], template["type"])}, from '
             f'{template.get("image") or (template.get("repository") or {}).get("url")}')
    check_fields(result, case.template)
    if case.source:
        check_source(result, template, case.source)
    check_logo(result, template.get('logo'))
    if template['type'] not in (1, 3):
        result.outcome = 'checked only, as swarm and edge templates can\'t be started here'
        return
    images = [template.get('image')]
    if template['type'] == 1:
        check_ports(result, template)
        check_ignored_fields(result, template)
    else:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as workdir:
            try:
                images = load_stack(result, template, workdir)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as err:
                images = []
                result.error(f'stack file could not be loaded ({reason(err)})')
    for image in filter(None, images):
        check_image(result, image)
    if result.errors:
        result.outcome = 'not started, fix the errors first'
    elif not start:
        result.outcome = 'checks passed, not started'
    else:
        deploy(result, template, timeout, portainer)

# --- Reporting ---

def cell(text):
    """Text that can't break out of a markdown table cell"""
    return html.escape(str(text), quote=False).replace('|', '\\|').replace('\n', ' ')

def fenced(text):
    """A code block that the text itself can't close early"""
    fence = '`' * max(3, max(map(len, re.findall(r'`+', text)), default=0) + 1)
    return [fence, text, fence]

def write_report(path, results):
    """A markdown table of results, then the details of anything that needs a look"""
    counts = [sum(r.icon == icon for r in results) for icon in ('✅', '⚠️', '❌')]
    lines = ['## 🧪 Template test results', '',
             f'{counts[0]} passed, {counts[1]} with warnings, {counts[2]} failed', '',
             '| | Template | From | Result |', '| --- | --- | --- | --- |']
    lines += [f'| {r.icon} | {cell(r.title)} | `{cell(r.where)}` | {cell(r.outcome)} |'
              for r in results]
    for r in (r for r in results if r.errors or r.warnings):
        summary = f'<summary>{r.icon} {html.escape(r.title)}</summary>'
        lines += ['', f'<details{" open" if r.errors else ""}>{summary}', '']
        lines += [f'- ❌ {cell(m)}' for m in r.errors] + [f'- ⚠️ {cell(m)}' for m in r.warnings]
        if len(r.status) > 1:
            lines += ['', '**Containers when it stopped**', ''] + [f'- {cell(s)}' for s in r.status]
        if r.logs.strip():
            whose = f'the {r.culprit} service\'s' if r.culprit else 'its'
            lines += ['', f'**Last {LOG_LINES} lines of {whose} logs**', '']
            lines += fenced(r.logs.strip())
        if r.errors and r.target:
            lines += ['', 'To run this test yourself, with Docker running: '
                          f'`python3 lib/test_template.py {shlex.quote(r.target)}`']
        lines += ['', '</details>']
    if counts[2]:
        lines += ['', f'The [template guide]({GUIDE}) covers what each field needs.']
    with open(path, 'a') as file:
        file.write('\n'.join(lines) + '\n')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('targets', nargs='*',
                        help='source names, template urls or files, or titles '
                             '(default: every app source)')
    parser.add_argument('--changed', metavar='REF',
                        help='test only what sources.csv and sources/ add or change since this ref')
    parser.add_argument('--no-start', action='store_true',
                        help='run the checks without starting anything')
    parser.add_argument('--timeout', type=int, default=180,
                        help='seconds to wait for each app to come up (default: %(default)s)')
    parser.add_argument('--report', metavar='FILE', help='append a markdown report to this file')
    args = parser.parse_args()
    banner('Test templates', 'Fetch, check and start templates the way Portainer would')

    targets = [t.strip() for t in args.targets if t.strip()]
    cases = changed_sources(args.changed) + changed_local(args.changed) if args.changed \
        else target_cases(targets)
    reports = list(filter(None, (args.report, os.environ.get('GITHUB_STEP_SUMMARY'))))
    if not cases:
        log.info('Nothing to test')
        for path in reports:
            with open(path, 'a') as file:
                file.write('## 🧪 Template test results\n\nNothing to start: no app source or '
                           'local template was added or changed.\n')
        return
    log.info(f'Testing {len(cases)} template{"s" if len(cases) != 1 else ""}')
    portainer = Portainer()  # only started if a stack needs deploying
    try:
        results = [test(case, not args.no_start, args.timeout, portainer) for case in cases]
    finally:
        portainer.close()

    for r in results:
        log.info(f'{r.icon} {r.title} ({r.where}): {r.outcome}')
    for path in reports:
        write_report(path, results)
    failed = [r.title for r in results if r.errors]
    if failed:
        log.error(f'{len(failed)} of {len(results)} failed: {", ".join(failed)}')
        sys.exit(1)

if __name__ == '__main__':
    main()
