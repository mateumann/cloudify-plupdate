#!/opt/manager/env/bin/python3

from os.path import join
from os import environ
from uuid import uuid4

from dsl_parser.constants import (PLUGIN_NAME_KEY,
                                  WORKFLOW_PLUGINS_TO_INSTALL,
                                  DEPLOYMENT_PLUGINS_TO_INSTALL,
                                  HOST_AGENT_PLUGINS_TO_INSTALL)

from manager_rest.constants import FILE_SERVER_BLUEPRINTS_FOLDER
from manager_rest.flask_utils import setup_flask_app, set_admin_current_user
from manager_rest.plugins_update.constants import (STATES,
                                                   ACTIVE_STATES)
from manager_rest.resource_manager import get_resource_manager
from manager_rest.storage import models, storage_manager, get_storage_manager
from manager_rest import config, resource_manager, utils

REST_HOME_DIR = '/opt/manager'
REST_CONFIG_PATH = join(REST_HOME_DIR, 'cloudify-rest.conf')
REST_SECURITY_CONFIG_PATH = join(REST_HOME_DIR, 'rest-security.conf')
REST_AUTHORIZATION_CONFIG_PATH = join(REST_HOME_DIR, 'authorization.conf')


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
    import pdb;  pdb.set_trace()  #noqa
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


def reevaluate_plugins_to_be_updated(temp_plan):
    print('reevaluate_plugins_to_be_updated')
    print(type(temp_plan))
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
    _sm = get_storage_manager()
    _rm = get_resource_manager(_sm)
    # import pdb; pdb.set_trace()  # noqa
    blueprints = _sm.list(models.Blueprint, all_tenants=True)
    for b in blueprints.items:
        print(f'Processing {b.id} blueprint')
        update_plugin(_sm, _rm, b)
