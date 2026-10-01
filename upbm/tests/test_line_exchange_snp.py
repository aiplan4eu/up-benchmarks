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

from upbm.domains.line_exchange_snp import LineExchangeSnpGenerator
from upbm.tests.base_domain_test import BaseDomainTest


def _configs(variant, **params):
    """A (domain configuration, instance configuration) pair for a variant."""
    domain_space = LineExchangeSnpGenerator.get_domain_parameter_space()
    domain_config = Configuration(domain_space, {"version": 1, "variant": variant})
    instance_space = LineExchangeSnpGenerator(domain_config).instance_parameter_space
    return domain_config, Configuration(instance_space, params)


class TestLineExchangeSnp(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "line-exchange-snp"

    @property
    def generator(self):
        return LineExchangeSnpGenerator

    def _get_configs(self):
        return [
            # two robots holding [3, 1], so one unit has to cross
            _configs(
                "bounded_5",
                n_robots=2,
                segment_length=10,
                q_0=3,
                q_1=1,
                q_2=0,
                q_3=0,
                q_4=0,
            ),
            # with these parameters the scramble draws [3, 1] as well
            _configs(
                "unbounded_random",
                n_robots=2,
                segment_length=2,
                mean_load=2,
                imbalance=50,
                seed=2,
            ),
            # shipped instance 0, named 3_10_50_10: three robots, D=10
            _configs("ipc", index=0),
        ]

    @property
    def plannable(self):
        # the two robot ones only; the IPC instances are much bigger
        return self._get_configs()[:2]

    @property
    def object_data(self):
        bounded, drawn, ipc = self._get_configs()
        return [
            (*bounded, [("robot", 2)]),
            (*drawn, [("robot", 2)]),
            (*ipc, [("robot", 3)]),
        ]

    @property
    def problem_actions(self):
        # lft, rgt, conn, disc, exch-lre, exch-rle
        return [(*config, 6) for config in self._get_configs()]

    @property
    def validation_cases(self):
        bounded, drawn, _ = self._get_configs()
        # Robot i owns the segment [D*i, D*(i+1)] and starts in its middle, so
        # two neighbours can only meet on the boundary between them. With D=10
        # each walks 5 steps there, they connect, pass one unit across, split
        # up and walk home again.
        exchange = ["(conn r0 r1)", "(exch-lre r0 r1)", "(disc r0 r1)"]
        meet = ["(rgt r0)"] * 5 + ["(lft r1)"] * 5
        home = ["(lft r0)"] * 5 + ["(rgt r1)"] * 5
        # The same trip with D=2 is one step each way. It only works if the
        # scramble really drew [3, 1], so it also pins the draw.
        short_trip = ["(rgt r0)", "(lft r1)"] + exchange + ["(lft r0)", "(rgt r1)"]
        return [
            (*bounded, "\n".join(meet + exchange + home), ValidationResultStatus.VALID),
            # exchanging without connecting first is not allowed
            (
                *bounded,
                "\n".join(meet + ["(exch-lre r0 r1)"] + home),
                ValidationResultStatus.INVALID,
            ),
            (*drawn, "\n".join(short_trip), ValidationResultStatus.VALID),
        ]
