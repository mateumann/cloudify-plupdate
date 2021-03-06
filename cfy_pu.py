#!/opt/manager/env/bin/python3

import click
import collections
from os.path import join
from os import environ
import requests
import yaml

from cloudify._compat import parse_qs

from dsl_parser.constants import (WORKFLOW_PLUGINS_TO_INSTALL,
                                  DEPLOYMENT_PLUGINS_TO_INSTALL,
                                  HOST_AGENT_PLUGINS_TO_INSTALL,
                                  PLUGIN_PACKAGE_NAME,
                                  PLUGIN_PACKAGE_VERSION)
from dsl_parser.models import Plan

from manager_rest.constants import FILE_SERVER_BLUEPRINTS_FOLDER
from manager_rest.flask_utils import (setup_flask_app, set_admin_current_user,
                                      get_tenant_by_name, set_tenant_in_app)
from manager_rest.storage import models, get_storage_manager
from manager_rest import config

REST_HOME_DIR = '/opt/manager'
REST_CONFIG_PATH = join(REST_HOME_DIR, 'cloudify-rest.conf')
REST_SECURITY_CONFIG_PATH = join(REST_HOME_DIR, 'rest-security.conf')
REST_AUTHORIZATION_CONFIG_PATH = join(REST_HOME_DIR, 'authorization.conf')

BLUEPRINT_LINE = 'blueprint_line'
CURRENT_VERSION = 'current_version'
EXECUTORS = [DEPLOYMENT_PLUGINS_TO_INSTALL,
             WORKFLOW_PLUGINS_TO_INSTALL,
             HOST_AGENT_PLUGINS_TO_INSTALL]

FINE = 'fine'
IMPORTS = 'imports'
IS_PINNED = True
IS_NOT_PINNED = False
IS_UNKNOWN = True
IS_NOT_UNKNOWN = False
REPO = 'repository'
SUGGESTED_VERSION = 'suggested_version'
UNKNOWN = 'unknown'
UPDATES = 'updates'
VERSIONS = 'versions'


def _version_to_key(version: str) -> float:
    vs = version.split('.')
    while len(vs) < 4:
        vs += '0'
    return (float(vs[0]) * 10 ** 6) + (float(vs[1]) * 10 ** 3) + \
        float(vs[2]) + (float(vs[3]) * 10 ** -3)


CLOUDIFY_PLUGINS = {
    'cloudify-aws-plugin': {
        VERSIONS: sorted(['2.4.2', '2.4.0', '2.3.5', '2.3.4', '2.3.2', '2.3.1',
                          '2.3.0', '2.2.1', '2.2.0', '2.1.0', '2.0.2', '2.0.1',
                          '2.0.0', '1.5.1.2', '1.5.1.1', '1.5.1', '1.5'],
                         key=_version_to_key, reverse=True),
        REPO: 'https://github.com/cloudify-cosmo/cloudify-aws-plugin',
    },
    'cloudify-azure-plugin': {
        VERSIONS: sorted(['3.0.3', '3.0.2', '3.0.1', '3.0.0', '2.1.10',
                          '2.1.9', '2.1.8', '2.1.7', '2.1.6', '2.1.5', '2.1.4',
                          '2.1.3', '2.1.1', '2.1.0', '2.0.0', '1.8.0', '1.7.3',
                          '1.7.2', '1.7.1', '1.7.0', '1.6.2', '1.6.1', '1.6.0',
                          '1.5.1.1', '1.5.1', '1.5.0', '1.4.3', '1.4.2',
                          '1.4'], key=_version_to_key, reverse=True),
        REPO: 'https://github.com/cloudify-cosmo/cloudify-azure-plugin',
    },
    'cloudify-gcp-plugin': {
        VERSIONS: sorted(['1.6.6', '1.6.5', '1.6.4', '1.6.2', '1.6.0', '1.5.1',
                          '1.5.0', '1.4.5', '1.4.4', '1.4.3', '1.4.2', '1.4.1',
                          '1.4.0', '1.3.0.1', '1.3.0', '1.2.0', '1.1.0',
                          '1.0.1'], key=_version_to_key, reverse=True),
        REPO: 'https://github.com/cloudify-cosmo/cloudify-gcp-plugin',
    },
    'cloudify-openstack-plugin': {
        VERSIONS: sorted(['3.2.18', '3.2.17', '2.14.20', '3.2.16', '2.14.19',
                          '2.14.18', '3.2.15', '3.2.14', '3.2.12', '3.2.11',
                          '2.14.17', '3.2.10', '2.14.16', '3.2.9', '2.14.15',
                          '2.14.14', '2.14.13', '3.2.8', '2.14.12', '3.2.7',
                          '3.2.6', '3.2.5', '3.2.4', '3.2.3', '2.14.11',
                          '3.2.2', '3.2.1', '2.14.10', '3.2.0', '3.1.1',
                          '2.14.9', '3.1.0', '3.0.0', '2.14.8', '2.14.7',
                          '2.14.6', '2.14.5', '2.14.4', '2.14.3', '2.14.2',
                          '2.14.1', '2.14.0', '2.13.1', '2.13.0', '2.12.0',
                          '2.11.1', '2.11.0', '2.10.0', '2.9.8', '2.9.6',
                          '2.9.5', '2.9.4', '2.9.3', '2.9.2', '2.9.1', '2.9.0',
                          '2.8.2', '2.8.1', '2.8.0', '2.7.6', '2.7.5',
                          '2.7.2.1', '2.7.4', '2.7.3', '2.7.2', '2.7.1',
                          '2.7.0', '2.6.0', '2.5.3', '2.5.2', '2.5.1', '2.5.0',
                          '2.4.1.1', '2.4.1', '2.4.0', '2.3.0', '2.2.0'],
                         key=_version_to_key, reverse=True),
        REPO: 'https://github.com/cloudify-cosmo/cloudify-openstack-plugin',
    },
    'cloudify-vsphere-plugin': {
        VERSIONS: sorted(['2.18.10', '2.18.9', '2.18.8', '2.18.7', '2.18.6',
                          '2.18.5', '2.18.4', '2.18.3', '2.18.2', '2.18.1',
                          '2.18.0', '2.18.0', '2.17.0', '2.16.2', '2.16.0',
                          '2.15.1', '2.15.0', '2.14.0', '2.13.1', '2.13.0',
                          '2.12.0', '2.9.3', '2.11.0', '2.10.0', '2.9.2',
                          '2.9.1', '2.9.0', '2.8.0', '2.7.0', '2.6.1', '2.2.2',
                          '2.6.0', '2.4.1', '2.5.0', '2.4.0', '2.3.0'],
                         key=_version_to_key, reverse=True),
        REPO: 'https://github.com/cloudify-cosmo/cloudify-vsphere-plugin',
    },
    'cloudify-terraform-plugin': {
        VERSIONS: sorted(['0.13.4', '0.13.3', '0.13.2', '0.13.1', '0.13.0',
                          '0.12.0', '0.11.0', '0.10', '0.9', '0.7'],
                         key=_version_to_key, reverse=True),
        REPO: 'https://github.com/cloudify-cosmo/cloudify-terraform-plugin',
    },
    'cloudify-ansible-plugin': {
        VERSIONS: sorted(['2.9.3', '2.9.2', '2.9.1', '2.9.0', '2.8.2', '2.8.1',
                          '2.8.0', '2.7.1', '2.7.0', '2.6.0', '2.5.0', '2.4.0',
                          '2.3.0', '2.2.0', '2.1.1', '2.1.0', '2.0.4', '2.0.3',
                          '2.0.2', '2.0.1', '2.0.0'],
                         key=_version_to_key, reverse=True),
        REPO: 'https://github.com/cloudify-cosmo/cloudify-ansible-plugin',
    },
    'cloudify-kubernetes-plugin': {
        VERSIONS: sorted(['2.8.3', '2.8.2', '2.8.1', '2.8.0', '2.7.2', '2.7.1',
                          '2.7.0', '2.6.5', '2.6.4', '2.6.3', '2.6.2', '2.6.0',
                          '2.5.0', '2.4.1', '2.4.0', '2.3.2', '2.3.1', '2.3.0',
                          '2.2.2', '2.2.1', '2.2.0', '2.1.0', '2.0.0.1',
                          '2.0.0',
                          '1.4.0', '1.3.1.1', '1.3.1', '1.3.0', '1.2.2',
                          '1.2.1',
                          '1.2.0', '1.1.0', '1.0.0'],
                         key=_version_to_key, reverse=True),
        REPO: 'https://github.com/cloudify-cosmo/cloudify-kubernetes-plugin',
    },

    # TODO mateumann fill in the rest

    'tosca-vcloud-plugin': {
        VERSIONS: sorted(['1.6.1', '1.6.0', '1.5.1', '1.5.0', '1.4.1'],
                         key=_version_to_key, reverse=True),
        REPO: 'https://github.com/cloudify-cosmo/tosca-vcloud-plugin',
    },

    # TODO mateumann testing (remove afterwards)
    'versioned-plugin': {
        VERSIONS: sorted(['0.0.2', '0.0.3', '0.0.4', '0.1.0', '0.1.1', '0.1.2',
                          '0.1.3', '0.2.0', '0.3.0', '0.3.2', '1.0.0', '1.0.1',
                          '1.0.9'], key=_version_to_key, reverse=True),
        REPO: 'https://github.com/mateumann/cloudify-plupdate',
    },
}


def blueprint_file_name(blueprint: models.Blueprint) -> str:
    return join(
        config.instance.file_server_root,
        FILE_SERVER_BLUEPRINTS_FOLDER,
        blueprint.tenant.name,
        blueprint.id,
        blueprint.main_file_name)


def spec_from_url(url: str) -> tuple:
    response = requests.get(url)
    if response.status_code != 200:
        return None, None
    try:
        plugin_yaml = yaml.safe_load(response.text)
    except yaml.YAMLError as ex:
        print(f'Cannot load imports from {url}: {ex}')
        return None, None
    for _, spec in plugin_yaml.get('plugins', {}).items():
        if spec.get(PLUGIN_PACKAGE_NAME) and \
                spec.get(PLUGIN_PACKAGE_VERSION):
            return spec[PLUGIN_PACKAGE_NAME], \
                   spec[PLUGIN_PACKAGE_VERSION]


def spec_from_import(plugin_line: str) -> tuple:
    # More or less copy of ResolverWithCatalogSupport._resolve_plugin_yaml_url
    spec = plugin_line.replace('plugin:', '', 1).strip()
    name, _, params = spec.partition('?')
    for filter_name, filter_value in parse_qs(params).items():
        if filter_name == 'version':
            if len(filter_value) == 1:
                return name, filter_value[0].strip()
            else:
                return name, None
    return name, None


def plugin_spec(import_line: str) -> tuple:
    if import_line.startswith('http://') or \
            import_line.startswith('https://'):
        name, version = spec_from_url(import_line)
        return IS_PINNED, IS_NOT_UNKNOWN, name, version
    elif import_line.startswith('plugin:'):
        name, version = spec_from_import(import_line)
        if version and version.startswith('>'):
            return IS_NOT_PINNED, IS_NOT_UNKNOWN, name, version
        elif not version:
            return IS_NOT_PINNED, IS_NOT_UNKNOWN, name, version
        else:
            return IS_PINNED, IS_NOT_UNKNOWN, name, version
    return IS_NOT_PINNED, IS_UNKNOWN, None, None


def plugins_in_a_plan(plan: Plan, plugin_names: tuple) -> collections.Iterable:
    for executor in [DEPLOYMENT_PLUGINS_TO_INSTALL,
                     WORKFLOW_PLUGINS_TO_INSTALL,
                     HOST_AGENT_PLUGINS_TO_INSTALL]:
        if executor not in plan:
            continue
        for plugin in plan[executor]:
            if plugin_names and \
                    plugin[PLUGIN_PACKAGE_NAME] not in plugin_names:
                continue
            if plugin[PLUGIN_PACKAGE_NAME] and \
                    plugin[PLUGIN_PACKAGE_VERSION]:
                yield plugin


def find_plugin_in_a_plan(plan: Plan,
                          plugin_names: tuple,
                          plugin_name: str) -> dict:
    for plugin in plugins_in_a_plan(plan, plugin_names):
        if plugin[PLUGIN_PACKAGE_NAME] == plugin_name:
            return plugin


def suggest_version(plugin_name: str, plugin_version: str) -> str:
    if plugin_name not in CLOUDIFY_PLUGINS:
        return plugin_version
    return CLOUDIFY_PLUGINS[plugin_name][VERSIONS][0]


def scan_blueprint(blueprint: models.Blueprint,
                   plugin_names: tuple) -> tuple:
    def add_mapping(mappings: dict, genre: str, content: object) -> dict:
        if genre not in mappings:
            mappings[genre] = []
        mappings[genre].append(content)
        return mappings

    file_name = blueprint_file_name(blueprint)
    try:
        with open(file_name, 'r') as f:
            try:
                imports = yaml.safe_load(f)[IMPORTS]
            except yaml.YAMLError as ex:
                print(f'Cannot load imports from {file_name}: {ex}')
                return None, None
    except FileNotFoundError:
        print(f'Blueprint file {file_name} does not exist')
        return None, None
    mappings = {}
    plugins_install_suggestions = {}
    for import_line in imports:
        is_pinned_version, is_unknown, plugin_name, plugin_version = \
            plugin_spec(import_line)
        if plugin_names and plugin_name not in plugin_names:
            continue
        if is_unknown:
            if not import_line.endswith('/types.yaml'):
                mappings = add_mapping(mappings, UNKNOWN, import_line)
            continue
        suggested_version = suggest_version(plugin_name, plugin_version)
        if not suggested_version:
            mappings = add_mapping(mappings, UNKNOWN, import_line)
            continue
        if plugin_name not in plugins_install_suggestions:
            plugins_install_suggestions[plugin_name] = suggested_version
        if not is_pinned_version:
            mappings = add_mapping(mappings, FINE, import_line)
            continue
        plugin_in_plan = find_plugin_in_a_plan(
            blueprint.plan, plugin_names, plugin_name
        )
        mappings = add_mapping(mappings, UPDATES, {
            plugin_name: {
                'import_line': import_line,
                CURRENT_VERSION: plugin_in_plan[PLUGIN_PACKAGE_VERSION],
                SUGGESTED_VERSION: suggested_version,
            }
        })
    return mappings, plugins_install_suggestions


@click.command()
@click.option('--tenant', default='default_tenant',
              help='Tenant name', )
@click.option('--plugin-name', 'plugin_names',
              multiple=True, help='Plugin(s) to update (you can provide '
                                  'multiple --plugin-name(s).')
@click.option('--blueprint', 'blueprint_ids',
              multiple=True, help='Blueprint(s) to update (you can provide '
                                  'multiple --blueprint(s).')
@click.option('--mapping', 'mapping_file', multiple=False, required=True,
              help='Provide a mapping file generated with ')
@click.option('--correct', is_flag=True, default=False,
              help='Update the blueprints using provided mapping file.')
def main(tenant, plugin_names, blueprint_ids, mapping_file, correct):
    # if correct and exists(mapping_file):
    #     raise Exception('Blueprints modification (--correct) is possible '
    #                     'only with an existing mapping file provided with '
    #                     '--mapping parameter.')

    set_tenant_in_app(get_tenant_by_name(tenant))
    _sm = get_storage_manager()
    filters = {'id': blueprint_ids} if blueprint_ids else None
    blueprints = _sm.list(models.Blueprint, filters=filters)
    mappings, install_suggestions = {}, {}
    for b in blueprints.items:
        print(f'Processing {b.id} blueprint')
        mapping, install_suggestion = scan_blueprint(b, plugin_names)
        if install_suggestion:
            install_suggestions.update(install_suggestion)
        if mapping:
            mappings[b.id] = mapping
    with open(mapping_file, 'w') as f:
        yaml.dump(mappings, f, default_flow_style=False)
    from pprint import pprint
    print(f'Make sure those plugins are installed (in suggested versions):')
    pprint(install_suggestions)


if __name__ == '__main__':
    for value, envvar in [
        (REST_CONFIG_PATH, 'MANAGER_REST_CONFIG_PATH'),
        (REST_SECURITY_CONFIG_PATH, 'MANAGER_REST_SECURITY_CONFIG_PATH'),
        (REST_AUTHORIZATION_CONFIG_PATH,
         'MANAGER_REST_AUTHORIZATION_CONFIG_PATH'),
    ]:
        if value is not None:
            environ[envvar] = value

    config.instance.load_configuration()
    app = setup_flask_app()
    set_admin_current_user(app)
    main()
