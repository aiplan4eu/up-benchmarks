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

from upbm.domains.temporal_plant_watering import TemporalPlantWateringGenerator
from upbm.tests.base_domain_test import BaseDomainTest


class TestTemporalPlantWatering(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "temporal-plant-watering"

    @property
    def generator(self):
        return TemporalPlantWateringGenerator

    def _get_configs(self):
        default_config = (
            TemporalPlantWateringGenerator.get_domain_parameter_space().get_default_configuration()
        )
        gen = TemporalPlantWateringGenerator(default_config)
        instance_space = gen.instance_parameter_space
        # 3x3 grid, pump in the middle. agent1 starts at (1, 1), agent2 at
        # (1, 2), and the only plant sits in the top-left corner (1, 3).
        instance_1 = Configuration(
            instance_space,
            {
                "size": 3,
                "n_plants": 1,
                "pour": 1,
                "n_agents": 2,
                "tap_x": 2,
                "tap_y": 2,
            },
        )
        # Same grid, but three agents fill the left column, so the plants
        # start at (2, 3) and go round the top-right corner: (2, 3), (3, 3)
        # and (3, 2).
        instance_2 = Configuration(
            instance_space,
            {
                "size": 3,
                "n_plants": 3,
                "pour": 1,
                "n_agents": 3,
                "tap_x": 2,
                "tap_y": 2,
            },
        )
        return [(default_config, instance_1), (default_config, instance_2)]

    @property
    def plannable(self):
        return self._get_configs()[:1]

    @property
    def object_data(self):
        instances = self._get_configs()
        return [
            (*instances[0], [("agent", 2), ("plant", 1), ("pump", 1)]),
            (*instances[1], [("agent", 3), ("plant", 3), ("pump", 1)]),
        ]

    @property
    def problem_actions(self):
        instances = self._get_configs()
        return [(*instances[0], 12), (*instances[1], 12)]

    @property
    def validation_cases(self):
        instances = self._get_configs()
        # agent1 fetches the pump and carries it to the plant, then agent2
        # opens it at the tap and agent1 pours while it is open.
        one_plant = """
        0: (move_right agent1)
        1: (move_up agent1)
        2: (take_pump agent1 pump1)
        3: (move_left_with_pump agent1 pump1)
        4: (move_up_with_pump agent1 pump1)
        5: (move_right agent2)
        6: (open_water_pump agent2 pump1) [10]
        7: (pour agent1 pump1 plant1)
        """
        # agent1 carries the pump round the three plants, and agent2 stays at
        # the tap and opens it once per plant.
        two_plants = """
        0: (move_right agent1)
        1: (move_up agent1)
        2: (take_pump agent1 pump1)
        3: (move_up_with_pump agent1 pump1)
        4: (move_right agent2)
        5: (open_water_pump agent2 pump1) [10]
        6: (pour agent1 pump1 plant1)
        16: (move_right_with_pump agent1 pump1)
        17: (open_water_pump agent2 pump1) [10]
        18: (pour agent1 pump1 plant2)
        """
        three_plants = (
            two_plants
            + """
        28: (move_down_with_pump agent1 pump1)
        29: (open_water_pump agent2 pump1) [10]
        30: (pour agent1 pump1 plant3)
        """
        )
        return [
            (*instances[0], one_plant, ValidationResultStatus.VALID),
            (*instances[1], three_plants, ValidationResultStatus.VALID),
            # Every step is applicable, but plant3 stays dry.
            (*instances[1], two_plants, ValidationResultStatus.INVALID),
        ]
