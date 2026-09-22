# Copyright 2026 Unified Planning library and its maintainers
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ConfigSpace import Configuration
from unified_planning.engines.plan_validator import SequentialPlanValidator
from unified_planning.engines.results import ValidationResultStatus

from upbm.domains.expedition import ExpeditionGenerator
from upbm.io import parse_plan_string
from upbm.tests.base_domain_test import BaseDomainTest
from upbm.utils import get_reduced_instance_space


def _domain_config():
    return ExpeditionGenerator.get_domain_parameter_space().get_default_configuration()


def _params(**overrides) -> Configuration:
    """A full instance configuration, the IPC expedition unless told otherwise.

    Every parameter has to be present, so an override is a change to the two
    sleds of capacity 4 the shipped set uses.
    """
    space = ExpeditionGenerator(_domain_config()).instance_parameter_space
    values = dict(space.get_default_configuration())
    values.update(overrides)
    return Configuration(space, values)


class TestExpedition(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "expedition"

    @property
    def generator(self):
        return ExpeditionGenerator

    def _get_configs(self):
        config = _domain_config()
        return [
            (config, _params(n_waypoints=2, n_chains=1)),
            (config, _params(n_waypoints=3, n_chains=1)),
            (config, _params(n_waypoints=3, n_chains=2)),
            (config, _params(n_waypoints=6, n_chains=1, n_sleds=1)),
        ]

    @property
    def plannable(self):
        return self._get_configs() + [
            (
                _domain_config(),
                _params(n_waypoints=3, n_chains=1, n_sleds=1, sled_capacity=6),
            ),
        ]

    @property
    def object_data(self):
        tiny, short, two_chains, len_6 = self._get_configs()
        return [
            (*tiny, [("sled", 2), ("waypoint", 2)]),
            (*short, [("sled", 2), ("waypoint", 3)]),
            (*two_chains, [("sled", 2), ("waypoint", 6)]),
            (*len_6, [("sled", 1), ("waypoint", 6)]),
            (
                _domain_config(),
                _params(n_waypoints=2, n_chains=4, n_sleds=4),
                [("sled", 4), ("waypoint", 8)],
            ),
        ]

    @property
    def problem_actions(self):
        # move_forwards, move_backwards, store_supplies, retrieve_supplies
        return [(*config, 4) for config in self._get_configs()]

    @property
    def validation_cases(self):
        domain_config, i_3 = self._get_configs()[3]
        valid_i_3 = """
        (retrieve_supplies s0 wa0)\n
        (retrieve_supplies s0 wa0)\n
        (retrieve_supplies s0 wa0)\n
        (move_forwards s0 wa0 wa1)\n
        (store_supplies s0 wa1)\n
        (move_backwards s0 wa1 wa0)\n
        (retrieve_supplies s0 wa0)\n
        (retrieve_supplies s0 wa0)\n
        (retrieve_supplies s0 wa0)\n
        (move_forwards s0 wa0 wa1)\n
        (retrieve_supplies s0 wa1)\n
        (move_forwards s0 wa1 wa2)\n
        (move_forwards s0 wa2 wa3)\n
        (move_forwards s0 wa3 wa4)\n
        (move_forwards s0 wa4 wa5)\n
        """

        empty_plan = ""

        invalid_i_3 = """
        (retrieve_supplies s0 wa0)\n
        (retrieve_supplies s0 wa0)\n
        (retrieve_supplies s0 wa0)\n
        (move_forwards s0 wa0 wa1)\n
        (move_backwards s0 wa1 wa0)\n
        (retrieve_supplies s0 wa0)\n
        (retrieve_supplies s0 wa0)\n
        (retrieve_supplies s0 wa0)\n
        (move_forwards s0 wa0 wa1)\n
        (retrieve_supplies s0 wa1)\n
        (move_forwards s0 wa1 wa2)\n
        (move_forwards s0 wa2 wa3)\n
        (move_forwards s0 wa3 wa4)\n
        (move_forwards s0 wa4 wa5)\n
        """

        return [
            (domain_config, i_3, valid_i_3, ValidationResultStatus.VALID),
            (
                domain_config,
                i_3,
                empty_plan,
                ValidationResultStatus.INVALID,
            ),
            (
                domain_config,
                i_3,
                invalid_i_3,
                ValidationResultStatus.INVALID,
            ),
        ]
