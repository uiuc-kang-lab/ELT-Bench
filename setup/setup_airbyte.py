"""Import the ELT manifest, publish its connector, and write local credentials."""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.error
import urllib.request

import yaml

ROOT = Path(__file__).resolve().parent


class SetupError(Exception):
    pass


class Airbyte:
    def __init__(self, url, username, password):
        self.url = url.rstrip('/') + '/api/v1/'
        auth = base64.b64encode(f'{username}:{password}'.encode()).decode()
        self.headers = {'Content-Type': 'application/json', 'Authorization': 'Basic ' + auth}

    def post(self, endpoint, body):
        request = urllib.request.Request(
            self.url + endpoint, json.dumps(body).encode(), self.headers
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            # Server responses can contain configuration secrets; do not print them.
            raise SetupError(
                f'Airbyte {endpoint}: HTTP {exc.code}. Check credentials, runtime '
                'compatibility, and Airbyte server logs.'
            ) from None
        except urllib.error.URLError:
            raise SetupError(f'Cannot reach Airbyte at {self.url}') from None


def local_credentials():
    """Read credentials from the local abctl cluster without logging secrets."""
    docker = ['docker'] if os.geteuid() == 0 else ['sudo', '-n', 'docker']
    command = docker + [
        'exec', os.environ.get('AIRBYTE_KIND_CONTAINER', 'airbyte-abctl-control-plane'),
        'kubectl', '--kubeconfig=/etc/kubernetes/admin.conf', '-n',
        os.environ.get('AIRBYTE_NAMESPACE', 'airbyte-abctl'),
    ]
    try:
        secret = json.loads(subprocess.check_output(
            command + ['get', 'secret', 'airbyte-auth-secrets', '-o', 'json'],
            stderr=subprocess.DEVNULL,
        ))['data']
        password = base64.b64decode(secret['instance-admin-password']).decode()
        # The email is not stored in the auth secret. Read only the username column.
        email = subprocess.check_output(command + [
            'exec', 'airbyte-db-0', '--', 'sh', '-c',
            'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At '
            '-c \'SELECT email FROM public.user;\'',
        ], stderr=subprocess.DEVNULL, text=True).strip().splitlines()
        if len(email) != 1 or not email[0]:
            raise SetupError('Multiple/no Airbyte users: set AIRBYTE_USERNAME and AIRBYTE_PASSWORD.')
        return email[0], password
    except (subprocess.CalledProcessError, OSError, KeyError, ValueError):
        raise SetupError(
            'Cannot read local abctl credentials. Set AIRBYTE_USERNAME and '
            'AIRBYTE_PASSWORD, or fill airbyte/airbyte_credential.json.'
        ) from None


def unique(items, description):
    if len(items) > 1:
        raise SetupError(f'Multiple matching {description}; resolve the duplicate names first.')
    return items[0] if items else None


def provision(api, manifest, name, workspace_id=None):
    workspaces = api.post('workspaces/list', {})['workspaces']
    if workspace_id:
        workspace = unique([w for w in workspaces if w['workspaceId'] == workspace_id], 'workspaces')
    else:
        workspace = unique(workspaces, 'workspaces (set AIRBYTE_WORKSPACE_ID)')
    if not workspace:
        raise SetupError('Workspace not found. Check AIRBYTE_WORKSPACE_ID.')
    workspace_id = workspace['workspaceId']
    scope = {'workspaceId': workspace_id}
    projects = api.post('connector_builder_projects/list', scope)['projects']
    project = unique([p for p in projects if p['name'] == name], 'Builder projects')
    definition_id = project.get('sourceDefinitionId') if project else None
    if definition_id:
        # Read the published version, even if a different draft is currently open.
        current = api.post('connector_builder_projects/get_with_manifest', {
            **scope, 'builderProjectId': project['builderProjectId'],
            'version': project['activeDeclarativeManifestVersion'],
        })['declarativeManifest']['manifest']
        if current != manifest:
            raise SetupError(
                f'Published connector "{name}" differs from the local YAML. '
                'Publish the intended changes in Builder before rerunning setup.'
            )
        print(f'Reusing published connector: {name}')
    else:
        # Fail before creating a draft if this CDK major version is unavailable.
        api.post('connector_builder_projects/get_base_image', {'manifest': manifest})
        details = {'name': name, 'draftManifest': manifest}
        if project:
            project_id = project['builderProjectId']
            api.post('connector_builder_projects/update', {
                **scope, 'builderProjectId': project_id, 'builderProject': details,
            })
        else:
            project_id = api.post('connector_builder_projects/create', {
                **scope, 'builderProject': details,
            })['builderProjectId']
        definition_id = api.post('connector_builder_projects/publish', {
            **scope, 'builderProjectId': project_id, 'name': name,
            'initialDeclarativeManifest': {
                'description': 'ELT Bench connector', 'version': 1,
                'manifest': manifest,
                'spec': {'connectionSpecification': manifest['spec']['connection_specification']},
            },
        })['sourceDefinitionId']
        print(f'Published connector: {name}')
    sources = api.post('sources/list', scope)['sources']
    source = unique([s for s in sources if s['name'] == name], 'Sources')
    if source and source['sourceDefinitionId'] != definition_id:
        raise SetupError(f'Source "{name}" already uses a different connector.')
    if not source:
        source = api.post('sources/create', {
            **scope, 'name': name, 'sourceDefinitionId': definition_id,
            'connectionConfiguration': {},
        })
        print(f'Created Source: {name}')
    else:
        print(f'Reusing Source: {name}')
    saved = api.post('sources/get', {'sourceId': source['sourceId']})
    if saved['sourceDefinitionId'] != definition_id or saved['workspaceId'] != workspace_id:
        raise SetupError('Saved Source does not match the expected workspace/connector.')
    return workspace_id, definition_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'elt_snowflake.yaml')
    parser.add_argument('--name', default='Elt Snowflake')
    parser.add_argument('--url', default=os.environ.get('AIRBYTE_URL', 'http://localhost:8000'))
    parser.add_argument('--credentials', type=Path, default=ROOT / 'airbyte/airbyte_credential.json')
    args = parser.parse_args()
    manifest = yaml.safe_load(args.manifest.read_text())
    if not isinstance(manifest, dict) or manifest.get('type') != 'DeclarativeSource':
        raise SetupError('Expected a DeclarativeSource YAML manifest.')
    spec = manifest.get('spec', {}).get('connection_specification')
    if not isinstance(spec, dict) or spec.get('required'):
        raise SetupError('This helper expects a connector requiring no Source configuration.')
    credentials = json.loads(args.credentials.read_text()) if args.credentials.exists() else {}
    username = os.environ.get('AIRBYTE_USERNAME', credentials.get('username', ''))
    password = os.environ.get('AIRBYTE_PASSWORD', credentials.get('password', ''))
    if not username or not password or username.startswith('<') or password.startswith('<'):
        username, password = local_credentials()
    api = Airbyte(args.url, username, password)
    workspace_id, definition_id = provision(
        api, manifest, args.name,
        os.environ.get('AIRBYTE_WORKSPACE_ID') or credentials.get('workspace_id') or None,
    )
    credentials.update(username=username, password=password,
                       workspace_id=workspace_id, api_definition_id=definition_id)
    args.credentials.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=args.credentials.parent, prefix='.airbyte-credentials-')
    try:
        with os.fdopen(fd, 'w') as output:
            json.dump(credentials, output, indent=2)
            output.write('\n')
        os.replace(temporary, args.credentials)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(f'Credentials saved (mode 600): {args.credentials}')


if __name__ == '__main__':
    try:
        main()
    except (SetupError, OSError, ValueError, KeyError) as exc:
        raise SystemExit(f'Airbyte setup failed: {exc}') from None
