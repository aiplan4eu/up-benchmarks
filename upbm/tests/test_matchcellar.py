from upbm.tests.base_domain_test import BaseDomainTest
from upbm.domains.matchcellar import MatchCellarGenerator
from unified_planning.engines.results import ValidationResultStatus
from ConfigSpace import Configuration


class TestMatchcellar(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "matchcellar"

    @property
    def generator(self):
        return MatchCellarGenerator

    def _get_configs(self):
        default_config = (
            MatchCellarGenerator.get_domain_parameter_space().get_default_configuration()
        )
        gen = MatchCellarGenerator(default_config)
        instance_space = gen.instance_parameter_space
        instance_1 = Configuration(instance_space, {"n_matches": 3, "n_fuses": 4})
        instance_2 = Configuration(instance_space, {"n_matches": 2, "n_fuses": 2})
        return [(default_config, instance_1), (default_config, instance_2)]

    @property
    def plannable(self):
        return self._get_configs()

    @property
    def object_data(self):
        instances = self._get_configs()

        object_data = []
        object_data.append((*instances[0], [("match", 3), ("fuse", 4)]))
        object_data.append((*instances[1], [("match", 2), ("fuse", 2)]))
        return object_data

    @property
    def problem_actions(self):

        instances = self._get_configs()
        problem_actions = []
        problem_actions.append((*instances[0], 2))
        problem_actions.append((*instances[1], 2))
        return problem_actions

    @property
    def validation_cases(self):
        instances = self._get_configs()

        validation_cases = []
        plan_string = """
        0: (light_match match1) [5]
        0.01: (mend_fuse fuse0 match1) [2]
        2.05: (mend_fuse fuse1 match1) [2]
        """
        validation_cases.append(
            (*instances[1], plan_string, ValidationResultStatus.VALID)
        )
        return validation_cases
