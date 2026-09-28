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

from typing import Any, Dict, List, Tuple

from ConfigSpace import Configuration

from unified_planning.engines.plan_validator import ValidationResultStatus

from upbm.domains.rainbowttles import RainbowttlesGenerator
from upbm.tests.base_domain_test import BaseDomainTest


SMALL = {
    "capacity": 4,
    "n_colours": 2,
    "bottles_per_colour": 1,
    "n_spare_bottles": 2,
    "scramble_steps": 3,
    "seed": 42,
}

EXAMPLE_SHAPES = [
    (3, 1, 2, 6),
    (6, 1, 3, 14),
    (8, 2, 3, 32),
    (10, 2, 4, 41),
]


class TestRainbowttles(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self) -> str:
        return "rainbowttles"

    @property
    def generator(self) -> Any:
        return RainbowttlesGenerator

    def _get_configs(self, **overrides) -> Tuple[Configuration, Configuration]:
        domain_space = RainbowttlesGenerator.get_domain_parameter_space()
        domain_config = Configuration(
            domain_space, values={"version": 1, "variant": "random"}
        )
        gen = RainbowttlesGenerator(domain_config)
        values: Dict[str, Any] = dict(SMALL)
        values.update(overrides)
        return domain_config, Configuration(gen.instance_parameter_space, values=values)

    def _ipc_configs(self, index: int) -> Tuple[Configuration, Configuration]:
        """The "ipc" variant rebuilding one shipped instance."""
        domain_space = RainbowttlesGenerator.get_domain_parameter_space()
        domain_config = Configuration(
            domain_space, values={"version": 1, "variant": "ipc"}
        )
        gen = RainbowttlesGenerator(domain_config)
        return domain_config, Configuration(
            gen.instance_parameter_space, values={"index": index}
        )

    @property
    def validation_cases(
        self,
    ) -> List[Tuple[Configuration, Configuration, str, ValidationResultStatus]]:
        """The point of the whole port: solvability is built in, not checked.

        The scramble is a run of pours walked backwards, so playing them
        forwards and closing every bottle has to reach the goal. This stands
        in for the dataset diff the reproducing ports use - there is nothing
        to diff against here - so every IPC-sized shape is checked on three
        seeds rather than the whole thing resting on one instance.
        """
        cases: List[
            Tuple[Configuration, Configuration, str, ValidationResultStatus]
        ] = []
        for n_colours, per_colour, spares, steps in EXAMPLE_SHAPES:
            for seed in (0, 1, 2):
                domain_config, instance_config = self._get_configs(
                    n_colours=n_colours,
                    bottles_per_colour=per_colour,
                    n_spare_bottles=spares,
                    scramble_steps=steps,
                    seed=seed,
                )
                gen = RainbowttlesGenerator(domain_config)
                cases.append(
                    (
                        domain_config,
                        instance_config,
                        gen.get_witness_plan(instance_config),
                        ValidationResultStatus.VALID,
                    )
                )
        return cases

    @property
    def plannable(self) -> List[Tuple[Configuration, Configuration]]:
        return [self._get_configs()]

    @property
    def object_data(self):
        domain_config, instance_config = self._get_configs()
        # the bottle count = colours x bottles_per_colour + spares.
        # Colours have the extra empty marker.
        bigger_domain, bigger = self._get_configs(
            n_colours=5, bottles_per_colour=2, n_spare_bottles=3
        )
        return [
            # 2 x 1 + 2 = 4 bottles
            (domain_config, instance_config, [("bottle", 4), ("colour", 3)]),
            # 5 x 2 + 3 = 13 bottles
            (bigger_domain, bigger, [("bottle", 13), ("colour", 6)]),
            (*self._ipc_configs(11), [("bottle", 5), ("colour", 4)]),
            (*self._ipc_configs(50), [("bottle", 24), ("colour", 11)]),
        ]

    @property
    def problem_actions(self) -> List[Tuple[Configuration, Configuration, int]]:
        domain_config, instance_config = self._get_configs()
        return [(domain_config, instance_config, 4)]
