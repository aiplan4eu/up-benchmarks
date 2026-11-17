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

from typing import Any, List, Tuple

from ConfigSpace import Configuration
from unified_planning.engines.results import ValidationResultStatus

from upbm.domains.settlers_snp import SettlersSnpGenerator
from upbm.tests.base_domain_test import BaseDomainTest


PFILE1_PLAN = """
; location0 is woodland and a mountain, so it makes its own timber, wood and
; stone. Timber: 1 for the coal stack, 2 for the sawmill, 2 to saw into wood.
; A house costs 1 wood and 1 stone.
(buildcabin1 location0)
(buildquarry1 location0)
(felltimber1 location0)
(felltimber1 location0)
(felltimber1 location0)
(felltimber1 location0)
(felltimber1 location0)
(buildcoalstack1 location0)
(buildsawmill1 location0)
(sawwood1 location0)
(sawwood1 location0)
(breakstone1 location0)
(breakstone1 location0)
(buildhouse1 location0)
(buildhouse1 location0)

; The rail costs 1 wood and 1 iron at location1. The iron needs an ironworks
; (2 stone, 2 wood), ore from a mine (2 wood; location1 is metalliferous) and
; 2 coal. Timber: 5 to saw into wood, 2 for the sawmill, 1 for the coal stack,
; 2 to burn into coal, 1 for a cart.
(buildcabin1 location1)
(felltimber1 location1)
(felltimber1 location1)
(felltimber1 location1)
(felltimber1 location1)
(felltimber1 location1)
(felltimber1 location1)
(felltimber1 location1)
(felltimber1 location1)
(felltimber1 location1)
(felltimber1 location1)
(felltimber1 location1)
(buildsawmill1 location1)
(sawwood1 location1)
(sawwood1 location1)
(sawwood1 location1)
(sawwood1 location1)
(sawwood1 location1)
(buildcoalstack1 location1)
(burncoal1 location1)
(burncoal1 location1)
(buildmine1 location1)
(mineore1 location1)
; location1 is not a mountain, so its stone comes from a quarry at the
; neighbouring location4, one piece per trip since a cart holds one.
(buildcart1 location1 vehicle0)
(buildquarry1 location4)
(breakstone1 location4)
(breakstone1 location4)
(movecart1 vehicle0 location1 location4)
(load1 vehicle0 location4 stone)
(movecart1 vehicle0 location4 location1)
(unload1 vehicle0 location1 stone)
(movecart1 vehicle0 location1 location4)
(load1 vehicle0 location4 stone)
(movecart1 vehicle0 location4 location1)
(unload1 vehicle0 location1 stone)
(buildironworks1 location1)
(makeiron1 location1)
(buildrail1 location1 location2)
"""

# The goal asks for two houses, so the same plan with one house fewer must fail.
PFILE1_ONE_HOUSE_SHORT = PFILE1_PLAN.replace("(buildhouse1 location0)\n", "", 1)


class TestSettlersSnp(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self) -> str:
        return "settlers-snp"

    @property
    def generator(self) -> Any:
        return SettlersSnpGenerator

    def _get_configs(self, index: int) -> Tuple[Configuration, Configuration]:
        """A (domain config, instance config) pair for one shipped instance."""
        domain_space = SettlersSnpGenerator.get_domain_parameter_space()
        domain_config = Configuration(
            domain_space, values={"version": 1, "variant": "ipc"}
        )
        gen = SettlersSnpGenerator(domain_config)
        return domain_config, Configuration(
            gen.instance_parameter_space, values={"index": index}
        )

    @property
    def validation_cases(self):
        domain_config, pfile1 = self._get_configs(1)
        return [
            (domain_config, pfile1, PFILE1_PLAN, ValidationResultStatus.VALID),
            (
                domain_config,
                pfile1,
                PFILE1_ONE_HOUSE_SHORT,
                ValidationResultStatus.INVALID,
            ),
            (domain_config, pfile1, "", ValidationResultStatus.INVALID),
        ]

    @property
    def plannable(self) -> List[Tuple[Configuration, Configuration]]:
        # IPC instances are too hard to test here
        return []

    @property
    def object_data(self):
        return [
            (*self._get_configs(1), [("place", 5), ("vehicle", 5), ("resource", 6)]),
            (
                *self._get_configs(20),
                [("place", 15), ("vehicle", 10), ("resource", 6)],
            ),
        ]

    @property
    def problem_actions(self) -> List[Tuple[Configuration, Configuration, int]]:
        return [(*self._get_configs(1), 24)]
