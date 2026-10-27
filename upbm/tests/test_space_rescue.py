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

from upbm.domains.space_rescue import SpaceRescueGenerator
from upbm.tests.base_domain_test import BaseDomainTest


def _config(**params):
    """The domain configuration and an instance configuration, the defaults
    unless told otherwise."""
    domain_config = (
        SpaceRescueGenerator.get_domain_parameter_space().get_default_configuration()
    )
    space = SpaceRescueGenerator(domain_config).instance_parameter_space
    values = dict(space.get_default_configuration())
    values.update(params)
    return domain_config, Configuration(space, values)


# The smallest instance: one rover, alone.
ALONE = dict(n_sites=4, rover_capacity=3, n_leech=0, n_stranded=0, stash_total=0)
# Small enough for a planner, and still a rescue: the saviour r2 starts at s3,
# two steps from the charging station s4, with the 2 packs it needs to get
# there. r1 is stranded at s5, next to the station. Both go to s2.
RESCUE = dict(
    n_sites=5, rover_capacity=3, n_leech=0, n_stranded=1, stash_total=0, seed=2
)
RESCUE_PLAN = [
    "(pick_up r2 s3 q2)",
    "(drive r2 s3 s1)",
    "(drive r2 s1 s4)",
    "(recharge r2 s4)",
    "(drive r2 s4 s5)",
    "(drop r2 s5 q1)",
    "(pick_up r1 s5 q1)",
    "(drive r2 s5 s4)",
    "(recharge r2 s4)",
    "(drive r2 s4 s1)",
    "(drive r2 s1 s3)",
    "(drive r2 s3 s2)",
    "(drive r1 s5 s4)",
    "(recharge r1 s4)",
    "(drive r1 s4 s1)",
    "(drive r1 s1 s3)",
    "(drive r1 s3 s2)",
]
# Every role, several goal sites, slack and scattered stashes.
CROWD = dict(
    n_sites=10,
    rover_capacity=5,
    n_leech=2,
    n_stranded=1,
    n_randoms=1,
    n_goal_sites=3,
    slack=1,
    stash_density=30,
)


class TestSpaceRescue(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "space-rescue"

    @property
    def generator(self):
        return SpaceRescueGenerator

    @property
    def plannable(self):
        return [_config(**RESCUE)]

    @property
    def object_data(self):
        # amounts: the powers of two up to the capacity
        return [
            (*_config(), [("rover", 3), ("site", 12), ("amount", 3)]),
            (*_config(**ALONE), [("rover", 1), ("site", 4), ("amount", 2)]),
            (*_config(**CROWD), [("rover", 5), ("site", 10), ("amount", 3)]),
        ]

    @property
    def problem_actions(self):
        # drive, pick_up, drop, recharge
        return [(*_config(**params), 4) for params in ({}, ALONE, CROWD)]

    @property
    def validation_cases(self):
        """A plan for RESCUE, and two broken copies of it: without the drop
        that frees the stranded rover, and with a drop at the charging
        station, which the domain forbids. The recharge after that drop puts
        the pack back, so the drop's precondition is the only thing wrong."""
        no_drop = [a for a in RESCUE_PLAN if not a.startswith("(drop")]
        recharged = RESCUE_PLAN.index("(recharge r2 s4)") + 1
        drop_at_station = (
            RESCUE_PLAN[:recharged]
            + ["(drop r2 s4 q1)", "(recharge r2 s4)"]
            + RESCUE_PLAN[recharged:]
        )
        return [
            (*_config(**RESCUE), "\n".join(plan), expected)
            for plan, expected in (
                (RESCUE_PLAN, ValidationResultStatus.VALID),
                (no_drop, ValidationResultStatus.INVALID),
                (drop_at_station, ValidationResultStatus.INVALID),
            )
        ]
