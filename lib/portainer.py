"""A throwaway Portainer, so stack templates deploy through the real thing"""
import os
import secrets
import subprocess
import time

import requests

from log import get_logger

log = get_logger()

# Current LTS, pinned by digest as it gets the Docker socket. Bump both together
VERSION = '2.45.3'
IMAGE = f'portainer/portainer-ce:{VERSION}' \
        '@sha256:3609c307943bca8e5c492f69ddd6965df177208b50678a4cff28391c8dd4e96e'
DEPLOYING, ERROR = 3, 4  # Portainer's stack statuses for deploying and failed
DEPLOY_TIMEOUT = 600  # seconds for Portainer to clone, pull and start a stack

class PortainerError(Exception):
    """Portainer refused a request or failed a deploy, with its reason"""

def docker(*args, timeout=120):
    return subprocess.run(['docker', *args], check=True, text=True, capture_output=True,
                          timeout=timeout).stdout

def wait_for(what, check, timeout):
    """Polls check() until it returns something, or gives up after timeout"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found = check()
        if found:
            return found
        time.sleep(2)
    raise PortainerError(f'{what} took over {timeout}s')

class Portainer:
    """Starts on first use, serves the whole run, and close() removes it"""
    def __init__(self):
        self.name = f'test-portainer-{os.getpid()}'
        self.session = requests.Session()
        self.url = self.environment = self.failed = None
        self.launched = False

    def start(self):
        """Starts Portainer on this Docker, sets up an admin and logs in"""
        if self.url:
            return
        if self.failed:
            raise PortainerError(self.failed)
        self.launched = True
        try:
            # Only reachable from localhost, so the setup token isn't needed
            docker('run', '--detach', '--name', self.name, '--publish', '127.0.0.1::9000',
                   '--volume', '/var/run/docker.sock:/var/run/docker.sock',
                   '--volume', f'{self.name}:/data', IMAGE,
                   '--host', 'unix:///var/run/docker.sock', '--http-enabled', '--no-setup-token',
                   timeout=600)
            url = f'http://{docker("port", self.name, "9000/tcp").split()[0]}'
            wait_for('Portainer starting', lambda: self.answers(url), 60)
            self.url = url
            login = {'Username': 'admin', 'Password': secrets.token_urlsafe(24)}
            self.request('POST', '/api/users/admin/init', json=login)
            jwt = self.request('POST', '/api/auth', json=login)['jwt']
            self.session.headers['Authorization'] = f'Bearer {jwt}'
            # Portainer adds this Docker as an environment once the admin exists
            self.environment = wait_for('Portainer adding this Docker', lambda: [
                e['Id'] for e in self.request('GET', '/api/endpoints')], 30)[0]
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                requests.RequestException, PortainerError) as err:
            if isinstance(err, subprocess.CalledProcessError):
                err = (err.stderr.strip().splitlines() or ['no output'])[-1]
            self.url, self.failed = None, f'Portainer itself didn\'t start ({err})'
            logs = subprocess.run(['docker', 'logs', '--tail', '20', self.name], text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  check=False).stdout
            log.info(f'Last lines of Portainer\'s logs:\n{logs}')
            raise PortainerError(self.failed) from None
        log.info(f'Started Portainer {VERSION} at {self.url}')

    @staticmethod
    def answers(url):
        try:
            return requests.get(f'{url}/api/system/status', timeout=5).ok
        except requests.RequestException:
            return False

    def request(self, method, path, timeout=60, **kwargs):
        """Calls Portainer's API, raising with its message if it fails"""
        response = self.session.request(method, f'{self.url}{path}', timeout=timeout, **kwargs)
        if not response.ok:
            try:
                body = response.json()
                message = ': '.join(filter(None, (body.get('message'), body.get('details'))))
            except ValueError:
                message = response.text.strip()
            raise PortainerError(message or f'HTTP {response.status_code} from {path}')
        return response.json() if response.content else {}

    def deploy(self, name, env, repository, content=None):
        """Creates a stack like the app templates page does, from git or as text"""
        self.start()
        body = {'Name': name, 'FromAppTemplate': True,
                'Env': [{'name': key, 'value': value} for key, value in env.items()]}
        if content is None:
            method = 'repository'
            body |= {'RepositoryURL': repository['url'], 'ComposeFile': repository['stackfile']}
        else:
            method, body['StackFileContent'] = 'string', content
        stack = self.request('POST', f'/api/stacks/create/standalone/{method}',
                             params={'endpointId': self.environment}, json=body,
                             timeout=DEPLOY_TIMEOUT)
        self.deployed(stack['Id'])
        return stack['Id']

    def deployed(self, stack_id):
        """Waits for Portainer's background deploy, raising its error if it fails"""
        def finished():
            stack = self.request('GET', f'/api/stacks/{stack_id}')
            return stack if stack['Status'] != DEPLOYING else None

        stack = wait_for('Portainer deploying the stack', finished, DEPLOY_TIMEOUT)
        if stack['Status'] == ERROR:
            messages = [s['Message'] for s in stack.get('DeploymentStatus') or []
                        if s.get('Message')]
            raise PortainerError(messages[-1] if messages else 'it failed without saying why')

    def restart(self, stack_id):
        """Stop then start, so Portainer recreates the containers on the same volumes"""
        params = {'endpointId': self.environment}
        self.request('POST', f'/api/stacks/{stack_id}/stop', params=params, timeout=DEPLOY_TIMEOUT)
        self.request('POST', f'/api/stacks/{stack_id}/start', params=params, timeout=DEPLOY_TIMEOUT)

    def close(self):
        if self.launched:
            subprocess.run(['docker', 'rm', '--force', self.name], capture_output=True, check=False)
            subprocess.run(['docker', 'volume', 'rm', self.name], capture_output=True, check=False)
