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
from unified_planning.engines.results import ValidationResultStatus

from upbm.domains.petri_net import PetriNetGenerator
from upbm.tests.base_domain_test import BaseDomainTest


def _config(index):
    domain_config = (
        PetriNetGenerator.get_domain_parameter_space().get_default_configuration()
    )
    space = PetriNetGenerator(domain_config).instance_parameter_space
    return domain_config, Configuration(space, {"index": index})


def _to_tip(branch):
    """Send one token from the source down to the tip of a funnel branch."""
    return [
        "(create s0)",
        f"(fire-one-to-one s0 {branch}1)",
        f"(fire-one-to-one {branch}1 {branch}2)",
        f"(fire-one-to-one {branch}2 {branch}3)",
    ]


class TestPetriNet(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "petri-net"

    @property
    def generator(self):
        return PetriNetGenerator

    def _get_configs(self):
        """One shipped instance per net."""
        return [
            _config(1),  # prob06-1, net 0
            _config(8),  # prob07-4, net 1
            _config(20),  # prob10-4, net 2
        ]

    @property
    def plannable(self):
        return []

    @property
    def object_data(self):
        net_0, net_1, net_2 = self._get_configs()
        return [
            (*net_0, [("place", 26)]),
            (*net_1, [("place", 18)]),
            (*net_2, [("place", 13)]),
        ]

    @property
    def problem_actions(self):
        return [(*config, 8) for config in self._get_configs()]

    @property
    def validation_cases(self):
        prob10_4 = self._get_configs()[2]

        one_token = (
            _to_tip("a")
            + _to_tip("a")
            + _to_tip("b")
            + _to_tip("c")
            + [
                "(fire-one-to-one a3 d1)",
                "(fire-three-to-one a3 b3 c3 d2)",
                "(fire-two-to-one d1 d2 g)",
            ]
        )
        cases = [
            (*prob10_4, one_token * 2, ValidationResultStatus.VALID),
            (*prob10_4, one_token, ValidationResultStatus.INVALID),
            (*prob10_4, one_token * 2 + _to_tip("a"), ValidationResultStatus.INVALID),
        ]
        return [
            (domain_config, instance_config, "\n".join(plan), expected)
            for domain_config, instance_config, plan, expected in cases
        ]
