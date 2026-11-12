"""Tests templates the way Portainer deploys them: fetch, check, start with the defaults, probe"""
import argparse
import base64
import copy
import csv
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
from validate_sources import check_templates

log = get_logger()

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
LOCAL_DIR = os.path.join(ROOT, 'sources', 'local')
REPO = os.environ.get('GITHUB_REPOSITORY', 'lissy93/portainer-templates')
GUIDE = f'https://github.com/{REPO}/blob/main/.github/CREATING_A_TEMPLATE.md'
SETTLE = 15  # seconds an app must stay up before it counts as started

SECRET_HINT = re.compile(r'pass|secret|key|token|salt|required', re.IGNORECASE)
OPENSSL_HINT = re.compile(r'openssl rand -(hex|base64) (\d+)')
PINNED_REF = re.compile(r'^(?:[0-9a-f]{40}|v?\d+(?:\.\d+)+)$')
TYPE_SUFFIX = re.compile(rf'\s*\((?:{"|".join(TYPE_LABELS.values())})\)$')

class Case(NamedTuple):
    """One template to test, where it came from, or why it can't be"""
    title: str
    where: str
    template: dict = None
    problem: str = None
    source: sources_list.Source = None

class Result:
    """What testing one template found, logged as it goes"""
    def __init__(self, case):
        self.title, self.where = case.title, case.where
        self.errors, self.warnings, self.outcome, self.logs = [], [], 'not started', ''

    def error(self, message):
        log.error(f'{self.title}: {message}')
        self.errors.append(message)

    def warn(self, message):
        log.warning(f'{self.title}: {message}')
        self.warnings.append(message)

    @property
    def icon(self):
        return '❌' if self.errors else '⚠️' if self.warnings else '✅'

def run(*command, timeout=600, **kwargs):
    """Run a command and return its output, raising with its stderr if it fails"""
    return subprocess.run(command, check=True, text=True, capture_output=True,
                          timeout=timeout, **kwargs).stdout

def reason(err):
    """The last line a failed command printed, which is usually the useful one"""
    if isinstance(err, subprocess.TimeoutExpired):
        return f'timed out after {err.timeout}s'
    lines = (err.stderr or err.stdout or '').strip().splitlines()
    return lines[-1] if lines else f'exit code {err.returncode}'

@contextmanager
def section(title):
    """Fold each template's output into its own group in the Actions log"""
    ci = os.environ.get('GITHUB_ACTIONS')
    sys.stderr.write(f'::group::{title}\n' if ci else f'\n▶ {title}\n')
    try:
        yield
    finally:
        if ci:
            sys.stderr.write('::endgroup::\n')

def title_key(title):
    """A title as combine.py dedupes it, without the type it adds when a container and stack clash"""
    return normalize_string(TYPE_SUFFIX.sub('', title))

def load_json(path):
    with open(path) as file:
        return json.load(file)

def git_show(ref, path):
    """A file's content at a git ref, or None if it didn't exist there"""
    try:
        return run('git', '-C', ROOT, 'show', f'{ref}:{path}')
    except subprocess.CalledProcessError:
        return None

# --- Working out what to test ---

def source_cases(source, where):
    """The template an app source publishes, fetched as download.py would, or read from a file"""
    try:
        payload, error = (load_json(source.url), None) if os.path.isfile(source.url) \
            else sources_list.fetch_json(source.url)
    except ValueError as err:
        payload, error = None, err
    if error:
        return [Case(source.name, where, problem=f'could not fetch valid JSON ({error})')]
    templates = [t for t in sources_list.templates_in(payload, allow_bare=True) or [] if isinstance(t, dict)]
    if not templates:
        return [Case(source.name, where, problem='found no templates, so the build would skip it')]
    if len(templates) > sources_list.MAX_APP_TEMPLATES:
        return [Case(source.name, where, problem=f'holds {len(templates)} templates, but an app '
                     f'source may publish {sources_list.MAX_APP_TEMPLATES}, so the build would skip it')]
    return [Case(str(t.get('title', source.name)), where, t, source=source) for t in templates]

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
            log.info(f'Skipping {source.name}: it\'s a collection, and only app sources get started')
    return cases

def changed_local(ref):
    """Templates in sources/local/ that are new or changed since ref, or whose stack file is"""
    changed = set(run('git', '-C', ROOT, 'diff', '--name-only', ref).split())
    cases = []
    for name in sorted(f for f in os.listdir(LOCAL_DIR) if f.endswith('.json')):
        path = f'sources/local/{name}'
        try:
            templates = load_json(os.path.join(ROOT, path))['templates']
            old = json.loads(git_show(ref, path) or '{"templates": []}')['templates']
        except (ValueError, KeyError, TypeError) as err:
            cases.append(Case(name, path, problem=f'could not read its templates ({err})'))
            continue
        before = {json.dumps(t, sort_keys=True) for t in old}
        cases += [Case(str(t.get('title', name)), path, t) for t in templates if isinstance(t, dict)
                  and (json.dumps(t, sort_keys=True) not in before
                       or (t.get('repository') or {}).get('stackfile') in changed)]
    return cases

def target_cases(targets):
    """Each target as a source name, template url or file, or published title. None: every app"""
    sources, lines = {s.name: s for s in sources_list.load()}, csv_lines()
    if not targets:
        return [case for s in sources.values() if s.is_app
                for case in source_cases(s, f'sources.csv:{lines[s.name]}')]
    published = {}
    for template in load_json(os.path.join(ROOT, 'templates.json'))['templates']:
        for key in {normalize_string(template['title']), title_key(template['title'])}:
            published.setdefault(key, []).append(template)
    cases = []
    for target in targets:
        if target.startswith(('http://', 'https://')) or os.path.isfile(target):
            cases += source_cases(sources_list.Source(target, target, '', sources_list.APP), target)
        elif target in sources and sources[target].is_app:
            cases += source_cases(sources[target], f'sources.csv:{lines[target]}')
        elif target in sources:
            cases.append(Case(target, f'sources.csv:{lines[target]}', problem='is a collection, '
                              'so name the template you want from it by its title instead'))
        elif normalize_string(target) in published:
            cases += [Case(t['title'], 'templates.json', t) for t in published[normalize_string(target)]]
        else:
            cases.append(Case(target, 'input', problem='matches no source, url, file or published title'))
    return cases

# --- Checks that need nothing started ---

def check_fields(result, raw):
    """The same schema and completeness checks validate_sources.py runs, minus its prefixes"""
    errors, warnings = check_templates('', [raw])
    if not errors:
        log.info('✓ Fields match the schema')
    for message in errors:
        result.error(message.split('": ', 1)[-1])
    for message in warnings:
        result.warn(message.split('": ', 1)[-1])

def check_source(result, template, source):
    """Things only an app source can get wrong: a pinned url, or a copy that outranks it"""
    parts = urlparse(source.url).path.split('/')
    if urlparse(source.url).hostname == 'raw.githubusercontent.com' and len(parts) > 3 \
       and PINNED_REF.match(parts[3]):
        result.warn(f'url is pinned to {parts[3]}, so later changes to the template won\'t '
                    'flow through. Point it at a branch instead')
    if not source.maintainer or not isinstance(template.get('title'), str):
        return
    key = (title_key(template['title']), template['type'])
    for name in sorted(f for f in os.listdir(LOCAL_DIR) if f.endswith('.json')):
        try:
            local = load_json(os.path.join(LOCAL_DIR, name))['templates']
        except (ValueError, KeyError, TypeError):
            continue  # validate_sources.py reports a broken local file
        titles = {(title_key(str(t.get('title', ''))), t.get('type', 1)) for t in local if isinstance(t, dict)}
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
    """The tag has to exist with an amd64 build. arm64 is a bonus, since many hosts are a Pi"""
    try:
        found = json.loads(run('docker', 'buildx', 'imagetools', 'inspect',
                               '--format', '{{json .Image}}', image, timeout=120))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
        return result.error(f'image {image} can\'t be found ({reason(err)})')
    configs = [found] if 'architecture' in found else found.values()
    arches = {c.get('architecture') for c in configs if c.get('os') == 'linux'}
    log.info(f'✓ Found {image}, built for {", ".join(sorted(arches)) or "nothing on linux"}')
    if 'amd64' not in arches:
        result.error(f'image {image} has no amd64 build, only {", ".join(sorted(arches)) or "none"}')
    elif 'arm64' not in arches:
        result.warn(f'image {image} has no arm64 build, so it won\'t run on ARM hosts')

# --- Starting it ---

def form_value(var):
    """What a deploy sends for a field: its default, else a stand-in where a secret is due"""
    options = var.get('select') or []
    chosen = next((o for o in options if o.get('default')), options[0] if options else {})
    if var.get('default') or chosen:
        return var.get('default') or chosen['value']
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

def start_container(template, name):
    """docker run, as Portainer builds it from a container template, on random local ports"""
    args = ['docker', 'run', '--detach', '--name', name]
    if template.get('network') == 'host':
        args += ['--network', 'host']
    else:
        for port in template.get('ports', []):
            args += ['--publish', f'127.0.0.1::{port.rpartition(":")[2]}']
    for volume in template.get('volumes', []):
        mount = f'{volume["bind"]}:{volume["container"]}' if volume.get('bind') else volume['container']
        args += ['--volume', mount + (':ro' if volume.get('readonly') else '')]
    for key, value in form_values(template).items():
        args += ['--env', f'{key}={value}']
    if template.get('restart_policy'):
        args += ['--restart', template['restart_policy']]
    if template.get('privileged'):
        args.append('--privileged')
    if template.get('interactive'):
        args += ['--interactive', '--tty']
    run(*args, template['image'], *shlex.split(template.get('command') or ''))

def prepare_stack(template, workdir):
    """Clone the stack's repo as Portainer does, and resolve its compose file onto random ports"""
    repo = template['repository']
    checkout = ROOT
    if not repo['url'].rstrip('/').removesuffix('.git').lower().endswith(f'github.com/{REPO.lower()}'):
        checkout = os.path.join(workdir, 'repo')
        run('git', 'clone', '--quiet', '--depth', '1', repo['url'], checkout)
    env = os.environ | form_values(template)
    config = json.loads(run('docker', 'compose', '--file', os.path.join(checkout, repo['stackfile']),
                            'config', '--format', 'json', env=env))
    for service in config['services'].values():
        for port in service.get('ports', []):
            port.pop('published', None)
            port['host_ip'] = '127.0.0.1'
    path = os.path.join(workdir, 'compose.json')
    with open(path, 'w') as file:
        json.dump(config, file)
    return path, list(dict.fromkeys(s['image'] for s in config['services'].values() if s.get('image')))

def containers(selector):
    ids = run('docker', 'ps', '--all', '--quiet', '--filter', selector).split()
    return json.loads(run('docker', 'inspect', *ids)) if ids else []

def answers(port):
    """True once something on the port answers HTTP without a server error"""
    try:
        return requests.get(f'http://127.0.0.1:{port}/', timeout=5, allow_redirects=False).status_code < 500
    except requests.RequestException:
        return False

def watch(result, selector, timeout):
    """Wait for it to come up and answer, failing on a crash, a restart loop or a bad health check"""
    def fail(message):
        result.outcome = message
        result.error(message)

    started = time.monotonic()
    while True:
        found, waited = containers(selector), int(time.monotonic() - started)
        for c in found:
            state = c['State']
            name = (c['Config']['Labels'] or {}).get('com.docker.compose.service', 'the container')
            if c['RestartCount'] >= 3:
                return fail(f'{name} keeps restarting (exit code {state["ExitCode"]})')
            if state['Status'] == 'exited' and state['ExitCode']:
                return fail(f'{name} exited with code {state["ExitCode"]} after {waited}s')
            if state.get('Health', {}).get('Status') == 'unhealthy':
                return fail(f'{name} failed its health check')
        restarting = any(c['State']['Restarting'] for c in found)
        running = [c for c in found if c['State']['Running'] and not c['State']['Restarting']]
        if not running and not restarting:
            return fail(f'nothing was left running after {waited}s')
        starting = restarting or any(c['State'].get('Health', {}).get('Status') == 'starting'
                                     for c in running)
        ports = {}
        for c in running:
            published = c['NetworkSettings']['Ports'] or {}
            if c['HostConfig']['NetworkMode'] == 'host':
                exposed = c['Config'].get('ExposedPorts') or {}
                published = {port: [{'HostPort': port.split('/')[0]}] for port in exposed}
            ports |= {binding['HostPort']: port for port, bindings in published.items()
                      if port.endswith('/tcp') for binding in bindings or []}
        answered = next((ports[p] for p in ports if answers(p)), None) if ports else None
        if waited >= SETTLE and not starting and (answered or not ports):
            result.outcome = f'answered on {answered} after {waited}s' if answered \
                else f'still running after {waited}s, with no ports to check'
            log.info(f'✓ {result.outcome}')
            return True
        if waited >= timeout:
            what = 'it never finished starting' if starting else \
                f'nothing answered over HTTP on {", ".join(sorted(ports.values()))}'
            result.outcome = f'running, but {what} within {timeout}s'
            return result.warn(f'{result.outcome}. Fine if it doesn\'t speak HTTP, else check the logs')
        time.sleep(5)

def deploy(result, template, workdir, compose, timeout):
    """Start it with the form untouched, watch it, keep its logs, then remove it all"""
    name = f'test-{re.sub(r"[^a-z0-9]+", "-", result.title.lower()).strip("-")}-{os.getpid()}'
    stack = ['docker', 'compose', '--project-name', name, '--file', compose] if compose else None
    selector = f'label=com.docker.compose.project={name}' if stack else f'name=^{name}$'
    up = False
    try:
        log.info(f'Starting {template.get("image") or "the stack"}')
        if stack:
            run(*stack, 'up', '--detach', '--quiet-pull')
        else:
            start_container(template, name)
        up = watch(result, selector, timeout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
        result.outcome = 'failed to start'
        result.error(f'failed to start ({reason(err)})')
    finally:
        if not up and containers(selector):
            logs = [*stack, 'logs', '--tail', '30'] if stack else ['docker', 'logs', '--tail', '30', name]
            result.logs = subprocess.run(logs, text=True, check=False,
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
            log.info(f'Last lines of its logs:\n{result.logs}')
        cleanup = [*stack, 'down', '--volumes', '--rmi', 'all'] if stack else \
            ['docker', 'rm', '--force', '--volumes', name]
        subprocess.run(cleanup, capture_output=True, check=False)
        if not stack:
            subprocess.run(['docker', 'rmi', template['image']], capture_output=True, check=False)

def test(case, start, timeout):
    """Test one template, reporting anything unexpected as a failure rather than stopping the run"""
    result = Result(case)
    with section(f'{case.title} ({case.where})'):
        try:
            check(result, case, start, timeout)
        except Exception as err:
            result.outcome = 'test crashed'
            result.error(f'test crashed ({type(err).__name__}: {err})')
    return result

def check(result, case, start, timeout):
    """Run every check on one template, and start it if they all pass"""
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
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as workdir:
        compose, images = None, [template.get('image')]
        if template['type'] == 3:
            try:
                compose, images = prepare_stack(template, workdir)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
                result.error(f'stack file could not be loaded ({reason(err)})')
        for image in filter(None, images):
            check_image(result, image)
        if result.errors:
            result.outcome = 'not started, fix the errors first'
        elif not start:
            result.outcome = 'checks passed, not started'
        else:
            deploy(result, template, workdir, compose, timeout)

# --- Reporting ---

def write_report(path, results):
    """A markdown table of results, then the details of anything that needs a look"""
    counts = [sum(r.icon == icon for r in results) for icon in ('✅', '⚠️', '❌')]
    lines = ['## 🧪 Template test results', '',
             f'{counts[0]} passed, {counts[1]} with warnings, {counts[2]} failed', '',
             '| | Template | From | Result |', '| --- | --- | --- | --- |']
    lines += [f'| {r.icon} | {r.title} | `{r.where}` | {r.outcome} |' for r in results]
    for r in (r for r in results if r.errors or r.warnings):
        lines += ['', f'<details{" open" if r.errors else ""}><summary>{r.icon} {r.title}</summary>', '']
        lines += [f'- ❌ {m}' for m in r.errors] + [f'- ⚠️ {m}' for m in r.warnings]
        if r.logs.strip():
            lines += ['', '```', r.logs.strip(), '```']
        lines += ['', '</details>']
    if counts[2]:
        lines += ['', f'The [template guide]({GUIDE}) covers each field and how to test a fix.']
    with open(path, 'a') as file:
        file.write('\n'.join(lines) + '\n')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('targets', nargs='*',
                        help='source names, template urls or files, or published titles '
                             '(default: every app source)')
    parser.add_argument('--changed', metavar='REF',
                        help='test only what sources.csv and sources/ add or change since this git ref')
    parser.add_argument('--no-start', action='store_true', help='run the checks without starting anything')
    parser.add_argument('--timeout', type=int, default=180,
                        help='seconds to wait for each app to come up (default: %(default)s)')
    parser.add_argument('--report', metavar='FILE', help='append a markdown report to this file')
    args = parser.parse_args()
    banner('Test templates', 'Fetch, check and start templates the way Portainer would')

    targets = [t.strip() for t in args.targets if t.strip()]
    cases = changed_sources(args.changed) + changed_local(args.changed) if args.changed \
        else target_cases(targets)
    if not cases:
        log.info('Nothing to test')
        return
    log.info(f'Testing {len(cases)} template{"s" if len(cases) != 1 else ""}')
    results = [test(case, not args.no_start, args.timeout) for case in cases]

    for r in results:
        log.info(f'{r.icon} {r.title} ({r.where}): {r.outcome}')
    for path in filter(None, (args.report, os.environ.get('GITHUB_STEP_SUMMARY'))):
        write_report(path, results)
    failed = [r.title for r in results if r.errors]
    if failed:
        log.error(f'{len(failed)} of {len(results)} failed: {", ".join(failed)}')
        sys.exit(1)

if __name__ == '__main__':
    main()
