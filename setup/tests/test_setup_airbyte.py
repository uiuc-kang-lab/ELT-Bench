import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from setup_airbyte import provision, SetupError


class ProvisionTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {'version': '4.3.0', 'spec': {'connection_specification': {'type': 'object'}}}
        self.project = {'name': 'Elt Snowflake', 'builderProjectId': 'project',
                        'sourceDefinitionId': 'definition', 'activeDeclarativeManifestVersion': 1}
        self.source = {'name': 'Elt Snowflake', 'sourceId': 'source',
                       'workspaceId': 'workspace', 'sourceDefinitionId': 'definition'}
        self.calls = []
        self.responses = {
            'workspaces/list': {'workspaces': [{'workspaceId': 'workspace'}]},
            'connector_builder_projects/list': {'projects': [self.project]},
            'connector_builder_projects/get_with_manifest': {'declarativeManifest': {'manifest': self.manifest}},
            'connector_builder_projects/get_base_image': {},
            'connector_builder_projects/create': {'builderProjectId': 'project'},
            'connector_builder_projects/publish': {'sourceDefinitionId': 'definition'},
            'sources/list': {'sources': [self.source]},
            'sources/create': self.source,
            'sources/get': self.source,
        }
        def post(endpoint, body):
            self.calls.append((endpoint, body))
            response = self.responses[endpoint]
            if isinstance(response, Exception):
                raise response
            return copy.deepcopy(response)
        self.api = Mock()
        self.api.post.side_effect = post

    def test_reuses_published_source_without_mutation(self):
        for _ in range(2):
            self.assertEqual(provision(self.api, self.manifest, 'Elt Snowflake'), ('workspace', 'definition'))
        self.assertFalse(any(ep.endswith(('/create', '/update', '/publish')) for ep, _ in self.calls))
        read = next(body for ep, body in self.calls if ep.endswith('/get_with_manifest'))
        self.assertEqual(read['version'], 1)

    def test_first_install_creates_publishes_and_creates_source(self):
        self.responses['connector_builder_projects/list'] = {'projects': []}
        self.responses['sources/list'] = {'sources': []}
        provision(self.api, self.manifest, 'Elt Snowflake')
        endpoints = [ep for ep, _ in self.calls]
        self.assertLess(endpoints.index('connector_builder_projects/get_base_image'), endpoints.index('connector_builder_projects/create'))
        body = next(body for ep, body in self.calls if ep.endswith('/publish'))
        self.assertEqual(body['initialDeclarativeManifest']['manifest'], self.manifest)
        self.assertIn('sources/create', endpoints)

    def test_unsupported_runtime_does_not_create_draft(self):
        self.responses['connector_builder_projects/list'] = {'projects': []}
        self.responses['connector_builder_projects/get_base_image'] = SetupError('unsupported runtime')
        with self.assertRaises(SetupError):
            provision(self.api, self.manifest, 'Elt Snowflake')
        self.assertFalse(any(ep.endswith('/create') for ep, _ in self.calls))

    def test_changed_published_manifest_is_not_overwritten(self):
        changed = {**self.manifest, 'version': '6.33.4'}
        with self.assertRaisesRegex(SetupError, 'differs'):
            provision(self.api, changed, 'Elt Snowflake')
        self.assertFalse(any(ep.endswith(('/create', '/update', '/publish')) for ep, _ in self.calls))

    def test_multiple_workspaces_require_selection(self):
        self.responses['workspaces/list']['workspaces'].append({'workspaceId': 'other'})
        with self.assertRaisesRegex(SetupError, 'AIRBYTE_WORKSPACE_ID'):
            provision(self.api, self.manifest, 'Elt Snowflake')


if __name__ == '__main__':
    unittest.main()
