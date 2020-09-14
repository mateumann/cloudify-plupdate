#!/opt/manager/env/bin/python3

from os.path import join
from os import environ
from uuid import uuid4

from dsl_parser.constants import (PLUGIN_NAME_KEY,
                                  WORKFLOW_PLUGINS_TO_INSTALL,
                                  DEPLOYMENT_PLUGINS_TO_INSTALL,
                                  HOST_AGENT_PLUGINS_TO_INSTALL)

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

PACKAGE_NAME = 'package_name'
PACKAGE_VERSION = 'package_version'
VERSIONS = 'versions'
REPO = 'repository'


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
}


def validate_no_active_updates_per_blueprint(
        sm: storage_manager.SQLStorageManager,
        blueprint: models.Blueprint):
    active_updates = sm.list(
        models.PluginsUpdate,
        filters={'blueprint_id': blueprint.id, 'state': ACTIVE_STATES},
        all_tenants=True,
    )
    if active_updates:
        raise Exception(
            'There are plugins updates still active, update IDs: '
            '{0}'.format(', '.join(u.id for u in active_updates)))


def did_plugins_to_install_change(temp_plan, plan) -> bool:
    # Maintaining backward comparability for older blueprints
    if not plan.get(HOST_AGENT_PLUGINS_TO_INSTALL):
        plan[HOST_AGENT_PLUGINS_TO_INSTALL] = \
            utils.extract_host_agent_plugins_from_plan(plan)
    return any(
        did_executor_plugins_to_install_change(temp_plan, plan, executor)
        for executor in [DEPLOYMENT_PLUGINS_TO_INSTALL,
                         WORKFLOW_PLUGINS_TO_INSTALL,
                         HOST_AGENT_PLUGINS_TO_INSTALL])


def did_executor_plugins_to_install_change(
        temp_plan, plan, plugins_executor) -> bool:
    temp_plugins = temp_plan[plugins_executor]
    current_plugins = plan[plugins_executor]
    name_to_plugin = {p[PLUGIN_NAME_KEY]: p for p in current_plugins}
    return any(plugin for plugin in temp_plugins
               if plugin != name_to_plugin.get(plugin[PLUGIN_NAME_KEY], None))


def get_reevaluated_plan(rm: resource_manager.ResourceManager,
                         blueprint: models.Blueprint):
    blueprint_dir = join(
        config.instance.file_server_root,
        FILE_SERVER_BLUEPRINTS_FOLDER,
        blueprint.tenant.name,
        blueprint.id)
    temp_plan = rm.parse_plan(blueprint_dir,
                              blueprint.main_file_name,
                              config.instance.file_server_root)
    return temp_plan


def stage_plugin_update(sm: storage_manager.SQLStorageManager,
                        blueprint: models.Blueprint) -> models.PluginsUpdate:
    update_id = str(uuid4())
    plugins_update = models.PluginsUpdate(
        id=update_id,
        created_at=utils.get_formatted_timestamp(),
        forced=False)
    plugins_update.set_blueprint(blueprint)
    return sm.put(plugins_update)


def create_temp_blueprint_from(sm: storage_manager.SQLStorageManager,
                               rm: resource_manager.ResourceManager,
                               blueprint: models.Blueprint,
                               temp_plan) -> models.Blueprint:
    temp_blueprint_id = str(uuid4())
    kwargs = {
        'application_file_name': blueprint.main_file_name,
        'blueprint_id': temp_blueprint_id,
        'plan': temp_plan
    }
    # Make sure not to pass both private resource and visibility
    visibility = blueprint.visibility
    if visibility:
        kwargs['visibility'] = visibility
        kwargs['private_resource'] = None
    else:
        kwargs['visibility'] = None
        kwargs['private_resource'] = blueprint.private_resource
    temp_blueprint = rm.publish_blueprint_from_plan(**kwargs)
    temp_blueprint.is_hidden = True
    return sm.update(temp_blueprint)


def list_plugins_in_a_plan(temp_plan):
    return [plugin
            for plugin in temp_plan['deployment_plugins_to_install'] +
            temp_plan['workflow_plugins_to_install'] +
            temp_plan['host_agent_plugins_to_install']
            if plugin[PACKAGE_NAME] and plugin[PACKAGE_VERSION]]


def get_plugin_version(plugin_name, plugin_version):
    if plugin_name not in CLOUDIFY_PLUGINS:
        return plugin_version
    return CLOUDIFY_PLUGINS[plugin_name][VERSIONS][0]


def suggest_plugin_versions(plugins):
    suggestions = {}
    for plugin in plugins:
        suggestions[plugin[PACKAGE_NAME]] = get_plugin_version(
            plugin[PACKAGE_NAME], plugin[PACKAGE_VERSION])
    return suggestions


def reevaluate_plugins_to_be_updated(temp_plan):
    plugins_installed = list_plugins_in_a_plan(temp_plan)
    if not plugins_installed:
        return temp_plan
    plugins_suggested = suggest_plugin_versions(plugins_installed)
    print('reevaluate_plugins_to_be_updated')
    print(f'PLUGINS INSTALLED\n\t{plugins_installed}')
    print(f'PLUGINS SUGGESTED\n\t{plugins_suggested}')
    return temp_plan


def update_plugin(sm: storage_manager.SQLStorageManager,
                  rm: resource_manager.ResourceManager,
                  blueprint: models.Blueprint) -> models.PluginsUpdate:
    validate_no_active_updates_per_blueprint(sm, blueprint)
    temp_plan = get_reevaluated_plan(rm, blueprint)
    temp_plan = reevaluate_plugins_to_be_updated(temp_plan)
    update_required = did_plugins_to_install_change(temp_plan, blueprint.plan)
    deployments_to_update = [d.id for d in
                             sm.list(models.Deployment,
                                     filters={'blueprint_id': blueprint.id},
                                     sort={'id': 'asc'},
                                     all_tenants=True).items]
    update_required &= len(deployments_to_update) > 0
    plugins_update = stage_plugin_update(sm, blueprint)
    if update_required:
        plugins_update.deployments_to_update = deployments_to_update
        sm.update(plugins_update)
        temp_blueprint = create_temp_blueprint_from(sm, rm, blueprint,
                                                    temp_plan)
        plugins_update.temp_blueprint = temp_blueprint
        plugins_update.state = STATES.UPDATING
        sm.update(plugins_update)
    plugins_update.execution = rm.update_plugins(plugins_update,
                                                 not update_required)
    plugins_update.state = (STATES.NO_CHANGES_REQUIRED
                            if not update_required
                            else STATES.EXECUTING_WORKFLOW)
    return sm.update(plugins_update)


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
    set_tenant_in_app(get_tenant_by_name('default_tenant'))
    _sm = get_storage_manager()
    _rm = get_resource_manager(_sm)
    # import pdb; pdb.set_trace()  # noqa
    blueprints = _sm.list(models.Blueprint,
                          filters={'id': 'bp'},
                          all_tenants=True)
    for b in blueprints.items:
        print(f'Processing {b.id} blueprint')
        update_plugin(_sm, _rm, b)
