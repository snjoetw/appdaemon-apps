from configurable_automation import ConfigurableAutomation, Handler
from lib.actions import get_action
from lib.constraints import get_constraint
from lib.triggers import get_trigger


def create_handler(app, handler_config):
    do_parallel_actions = handler_config.get("do_parallel_actions", True)

    constraints = []
    constraint_configs = handler_config.get("constraints") or []
    for constraint_config in constraint_configs:
        constraints.append(get_constraint(app, constraint_config))

    actions = []
    action_configs = handler_config.get("actions", [])
    for action_config in action_configs:
        actions.append(get_action(app, action_config))

    return Handler(app, constraints, actions, do_parallel_actions)


class Automation(ConfigurableAutomation):
    def initialize(self):
        super().initialize()

        # keep all template variables so they can be used in component where jinja template is initialized
        self._variables = self.args.get("variables", {})

        for trigger_config in self.cfg.value("triggers"):
            # Initialize a trigger based on config
            trigger = get_trigger(self, trigger_config, self.trigger_handler)
            self.debug('Registered trigger={}'.format(trigger))

        constraint_configs = self.args.get("constraints") or []
        for constraint_config in constraint_configs:
            self._global_constraints.append(get_constraint(self, constraint_config))

        for handler_config in self.cfg.value("handlers"):
            handler = create_handler(self, handler_config)
            self._handlers.append(handler)
            self.debug('Registered handler={}'.format(handler))

        if self.args.get("cancel_job_when_no_match", False):
            self._handlers.append(create_handler(self, {
                "constraints": [],
                "actions": [{
                    "platform": "cancel_job",
                    "cancel_all": True,
                }]
            }))

    @property
    def variables(self):
        return self._variables
