#!/opt/manager/env/bin/python3

import click
import collections
from os.path import join
from os import environ
from uuid import uuid4
import yaml

from dsl_parser.constants import (PLUGIN_NAME_KEY,
                                  WORKFLOW_PLUGINS_TO_INSTALL,
                                  DEPLOYMENT_PLUGINS_TO_INSTALL,
                                  HOST_AGENT_PLUGINS_TO_INSTALL,
                                  PLUGIN_PACKAGE_NAME,
                                  PLUGIN_PACKAGE_VERSION)
from dsl_parser.models import Plan

from manager_rest.constants import FILE_SERVER_BLUEPRINTS_FOLDER
from manager_rest.flask_utils import (setup_flask_app, set_admin_current_user,
                                      get_tenant_by_name, set_tenant_in_app)
from manager_rest.plugins_update.constants import (STATES,
                                                   ACTIVE_STATES)
from manager_rest.resource_manager import get_resource_manager
from manager_rest.storage import models, storage_manager, get_storage_manager
from manager_rest import config, resource_manager, utils

REST_HOME_DIR = '/opt/manager'
REST_CONFIG_PATH = join(REST_HOME_DIR, 'cloudify-rest.conf')
REST_SECURITY_CONFIG_PATH = join(REST_HOME_DIR, 'rest-security.conf')
REST_AUTHORIZATION_CONFIG_PATH = join(REST_HOME_DIR, 'authorization.conf')

BLUEPRINT_LINE = 'blueprint_line'
CURRENT = 'current'
EXECUTORS = [DEPLOYMENT_PLUGINS_TO_INSTALL,
             WORKFLOW_PLUGINS_TO_INSTALL,
             HOST_AGENT_PLUGINS_TO_INSTALL]
IMPORTS = 'imports'
REPO = 'repository'
SOURCE = 'source'
SUGGESTED = 'suggested'
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
                        '2.2.2', '2.2.1', '2.2.0', '2.1.0', '2.0.0.1', '2.0.0',
                        '1.4.0', '1.3.1.1', '1.3.1', '1.3.0', '1.2.2', '1.2.1',
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


# There are some Cloudify helper functions  -->

# def validate_no_active_updates_per_blueprint(
#         sm: storage_manager.SQLStorageManager,
#         blueprint: models.Blueprint):
#     active_updates = sm.list(
#         models.PluginsUpdate,
#         filters={'blueprint_id': blueprint.id, 'state': ACTIVE_STATES},
#         all_tenants=True,
#     )
#     if active_updates:
#         raise Exception(
#             'There are plugins updates still active, update IDs: '
#             '{0}'.format(', '.join(u.id for u in active_updates)))
#
#
# def did_plugins_to_install_change(temp_plan: Plan, plan: Plan) -> bool:
#     # Maintaining backward comparability for older blueprints
#     if not plan.get(HOST_AGENT_PLUGINS_TO_INSTALL):
#         plan[HOST_AGENT_PLUGINS_TO_INSTALL] = \
#             utils.extract_host_agent_plugins_from_plan(plan)
#     return any(
#         did_executor_plugins_to_install_change(temp_plan, plan, executor)
#         for executor in EXECUTORS)
#
#
# def did_executor_plugins_to_install_change(
#         temp_plan: Plan, plan: Plan, plugins_executor) -> bool:
#     temp_plugins = temp_plan[plugins_executor]
#     current_plugins = plan[plugins_executor]
#     name_to_plugin = {p[PLUGIN_NAME_KEY]: p for p in current_plugins}
#     return any(plugin for plugin in temp_plugins
#                if plugin != name_to_plugin.get(plugin[PLUGIN_NAME_KEY], None))
#
#
# def get_reevaluated_plan(rm: resource_manager.ResourceManager,
#                          blueprint: models.Blueprint):
#     blueprint_dir = join(
#         config.instance.file_server_root,
#         FILE_SERVER_BLUEPRINTS_FOLDER,
#         blueprint.tenant.name,
#         blueprint.id)
#     temp_plan = rm.parse_plan(blueprint_dir,
#                               blueprint.main_file_name,
#                               config.instance.file_server_root)
#     return temp_plan
#
#
# def stage_plugin_update(sm: storage_manager.SQLStorageManager,
#                         blueprint: models.Blueprint) -> models.PluginsUpdate:
#     update_id = str(uuid4())
#     plugins_update = models.PluginsUpdate(
#         id=update_id,
#         created_at=utils.get_formatted_timestamp(),
#         forced=False)
#     plugins_update.set_blueprint(blueprint)
#     return sm.put(plugins_update)
#
#
# def create_temp_blueprint_from(sm: storage_manager.SQLStorageManager,
#                                rm: resource_manager.ResourceManager,
#                                blueprint: models.Blueprint,
#                                temp_plan) -> models.Blueprint:
#     temp_blueprint_id = str(uuid4())
#     kwargs = {
#         'application_file_name': blueprint.main_file_name,
#         'blueprint_id': temp_blueprint_id,
#         'plan': temp_plan
#     }
#     # Make sure not to pass both private resource and visibility
#     visibility = blueprint.visibility
#     if visibility:
#         kwargs['visibility'] = visibility
#         kwargs['private_resource'] = None
#     else:
#         kwargs['visibility'] = None
#         kwargs['private_resource'] = blueprint.private_resource
#     temp_blueprint = rm.publish_blueprint_from_plan(**kwargs)
#     temp_blueprint.is_hidden = True
#     return sm.update(temp_blueprint)

# These were some Cloudify helper functions  <--


def blueprint_file_name(blueprint: models.Blueprint) -> str:
    return join(
        config.instance.file_server_root,
        FILE_SERVER_BLUEPRINTS_FOLDER,
        blueprint.tenant.name,
        blueprint.id,
        blueprint.main_file_name)


# def get_plugin_version(name: str, version: str) -> str:
#     if name not in CLOUDIFY_PLUGINS:
#         return version
#     return CLOUDIFY_PLUGINS[name][VERSIONS][0]
#
#
# def suggest_plugin_versions(plugins: list) -> dict:
#     suggestions = {}
#     for plugin in plugins:
#         suggestions[plugin[PLUGIN_PACKAGE_NAME]] = {
#             OLD: plugin[PLUGIN_PACKAGE_VERSION],
#             SUGGESTED: get_plugin_version(
#                 plugin[PLUGIN_PACKAGE_NAME], plugin[PLUGIN_PACKAGE_VERSION]),
#         }
#     return suggestions


# def plugin_source(name: str, version: str) -> str:
#     if name not in CLOUDIFY_PLUGINS:
#         return None
#     return CLOUDIFY_PLUGINS[name][REPO] + f'/archive/{version}.zip'


def substitude_plugins(plugins: list, plugin_suggestions: dict) -> list:
    result = []
    for plugin in plugins:
        if plugin[PLUGIN_PACKAGE_NAME] in plugin_suggestions:
            suggestion = plugin_suggestions[plugin[PLUGIN_PACKAGE_NAME]]
            plugin[PLUGIN_PACKAGE_VERSION] = suggestion[SUGGESTED]
            plugin[SOURCE] = plugin_source(plugin[PLUGIN_PACKAGE_NAME],
                                           plugin[PLUGIN_PACKAGE_VERSION])
        result.append(plugin)
    return result


# def reevaluate_plugins_to_be_updated(blueprint: models.Blueprint,
#                                      temp_plan: Plan,
#                                      minor_only: bool,
#                                      plugin_names: tuple,
#                                      minor_except_names: tuple) -> Plan:
#     plugins_installed = list_plugins_in_a_plan(temp_plan)
#     if plugin_names:
#         plugins_installed = [p for p in plugins_installed
#                              if p[PACKAGE_NAME] in plugin_names]
#     if not plugins_installed:
#         return temp_plan
#     plugins_update_suggestions = suggest_plugin_versions(plugins_installed,
#                                                          minor_only,
#                                                          minor_except_names)
#     if not plugins_update_suggestions:
#         return temp_plan
#
#     # update plugins the plan
#     for executor in EXECUTORS:
#         if executor not in temp_plan:
#             continue
#         temp_plan[executor] = substitude_plugins(temp_plan[executor],
#                                                  plugins_update_suggestions)
#     return temp_plan


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


def import_line(imports: list, plugin_name: str) -> str:
    for line in imports:
        if plugin_name in line:
            return line


def suggest_version(plugin: dict, blueprint_line: str) -> str:

    def get_plugin_version(name: str, version: str) -> str:
        if name not in CLOUDIFY_PLUGINS:
            return version
        return CLOUDIFY_PLUGINS[name][VERSIONS][0]

    return get_plugin_version(plugin[PLUGIN_PACKAGE_NAME],
                              plugin[PLUGIN_PACKAGE_VERSION])


def scan_blueprint(sm: storage_manager.SQLStorageManager,
                   rm: resource_manager.ResourceManager,
                   blueprint: models.Blueprint,
                   plugin_names: tuple) -> dict:
    file_name = blueprint_file_name(blueprint)
    import pdb; pdb.set_trace()  # noqa
    try:
        with open(file_name, 'r') as f:
            try:
                imports = yaml.safe_load(f)[IMPORTS]
            except yaml.YAMLError as ex:
                print(f'Cannot load imports from {file_name}: {ex}')
                return {}
    except FileNotFoundError as ex:
        print(f'Blueprint file {file_name} does not exist')
        return {}
    print(f'imports {imports}')
    mappings = {}
    for plugin in plugins_in_a_plan(blueprint.plan, plugin_names):
        if plugin[PLUGIN_PACKAGE_NAME] in mappings:
            continue
        blueprint_line = import_line(imports, plugin[PLUGIN_PACKAGE_NAME])
        mappings[plugin[PLUGIN_PACKAGE_NAME]] = {
            CURRENT: plugin[PLUGIN_PACKAGE_VERSION],
            BLUEPRINT_LINE: blueprint_line,
            SUGGESTED: suggest_version(plugin, blueprint_line),
        }
    print(f'blueprint file name: {file_name}')
    return mappings


@click.command()
@click.option('--tenant', default='default_tenant',
              help='Tenant name')
@click.option('--plugin-name', 'plugin_names',
              multiple=True, help='Plugin(s) to update (you can provide '
                                  'multiple --plugin-name(s).')
@click.option('--blueprint', 'blueprint_ids',
              multiple=True, help='Blueprint(s) to update (you can provide '
                                  'multiple --blueprint(s).')
@click.option('--mapping', 'mapping_file', multiple=False,
              help='Provide a mapping file generated with ')
@click.option('--correct', is_flag=True, default=False,
              help='Update the blueprints using provided mapping file.')
def main(tenant, plugin_names, blueprint_ids, mapping_file, correct):
    if correct and not mapping_file:
        raise Exception('Blueprints modification (--correct) is possible '
                        'only with a mapping file provided with --mapping '
                        'parameter.')

    set_tenant_in_app(get_tenant_by_name(tenant))
    _sm = get_storage_manager()
    _rm = get_resource_manager(_sm)
    filters = {'id': blueprint_ids} if blueprint_ids else None
    #          = _sm.list(models.Blueprint, filters=filters, all_tenants=True)
    blueprints = _sm.list(models.Blueprint, filters=filters)
    for b in blueprints.items:
        print(f'Processing {b.id} blueprint')
        mapping = scan_blueprint(_sm, _rm, b, plugin_names)
        print(f'mapping {mapping}')


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
