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
from upbm.domains.space_rescue.space_rescue import VARIANTS
from upbm.tests.base_domain_test import BaseDomainTest


def _config(variant="base", **params):
    """The domain configuration and an instance configuration, the defaults
    unless told otherwise."""
    domain_config = Configuration(
        SpaceRescueGenerator.get_domain_parameter_space(),
        {"version": 1, "variant": variant},
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
# The same plan in the snp variant, where packs move 1 or 3 at a time: the
# pick-up of 2 becomes two of 1, and every recharge, from 0, is one of 3.
SNP_RESCUE_PLAN = [
    "(pick_up_1 r2 s3)",
    "(pick_up_1 r2 s3)",
    "(drive r2 s3 s1)",
    "(drive r2 s1 s4)",
    "(recharge_3 r2 s4)",
    "(drive r2 s4 s5)",
    "(drop_1 r2 s5)",
    "(pick_up_1 r1 s5)",
    "(drive r2 s5 s4)",
    "(recharge_3 r2 s4)",
    "(drive r2 s4 s1)",
    "(drive r2 s1 s3)",
    "(drive r2 s3 s2)",
    "(drive r1 s5 s4)",
    "(recharge_3 r1 s4)",
    "(drive r1 s4 s1)",
    "(drive r1 s1 s3)",
    "(drive r1 s3 s2)",
]
# The same plan in the classical variant, with the counts: drive's packs
# before and after; pick_up's site packs before and after, then the rover's,
# then its capacity; drop's rover packs before and after, then the site's;
# recharge's packs before and the capacity.
CLASSICAL_RESCUE_PLAN = [
    "(pick_up r2 s3 q2 n2 n0 n0 n2 n3)",
    "(drive r2 s3 s1 n2 n1)",
    "(drive r2 s1 s4 n1 n0)",
    "(recharge r2 s4 n0 n3)",
    "(drive r2 s4 s5 n3 n2)",
    "(drop r2 s5 q1 n2 n1 n0 n1)",
    "(pick_up r1 s5 q1 n1 n0 n0 n1 n3)",
    "(drive r2 s5 s4 n1 n0)",
    "(recharge r2 s4 n0 n3)",
    "(drive r2 s4 s1 n3 n2)",
    "(drive r2 s1 s3 n2 n1)",
    "(drive r2 s3 s2 n1 n0)",
    "(drive r1 s5 s4 n1 n0)",
    "(recharge r1 s4 n0 n3)",
    "(drive r1 s4 s1 n3 n2)",
    "(drive r1 s1 s3 n2 n1)",
    "(drive r1 s3 s2 n1 n0)",
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
        return [_config(variant, **RESCUE) for variant in VARIANTS]

    @property
    def object_data(self):
        # amounts: the powers of two up to the capacity (none in snp); counts:
        # n0 up to max(site_cap * C, C + slack, stash_total * C), site_cap 2
        return [
            (*_config(), [("rover", 3), ("site", 12), ("amount", 3)]),
            (*_config(**ALONE), [("rover", 1), ("site", 4), ("amount", 2)]),
            (*_config(**CROWD), [("rover", 5), ("site", 10), ("amount", 3)]),
            (*_config("snp"), [("rover", 3), ("site", 12)]),
            (*_config("classical"), [("amount", 3), ("count", 9)]),
            (*_config("classical", **ALONE), [("amount", 2), ("count", 7)]),
            (*_config("classical", **CROWD), [("amount", 3), ("count", 11)]),
        ]

    @property
    def problem_actions(self):
        # drive, pick_up, drop, recharge; in snp, each of the last three
        # twice, for 1 and 3 packs
        n_actions = {"base": 4, "snp": 7, "classical": 4}
        return [
            (*_config(variant, **params), n_actions[variant])
            for variant in VARIANTS
            for params in ({}, ALONE, CROWD)
        ]

    @property
    def validation_cases(self):
        """A plan for RESCUE, and two broken copies of it: without the drop
        that frees the stranded rover, and with a drop at the charging
        station, which the domain forbids. The recharge after that drop puts
        the pack back, so the drop's precondition is the only thing wrong.
        The same plan in the other variants, valid, and without the drop."""
        recharged = RESCUE_PLAN.index("(recharge r2 s4)") + 1
        drop_at_station = (
            RESCUE_PLAN[:recharged]
            + ["(drop r2 s4 q1)", "(recharge r2 s4)"]
            + RESCUE_PLAN[recharged:]
        )
        cases = [("base", drop_at_station, ValidationResultStatus.INVALID)]
        for variant, plan in (
            ("base", RESCUE_PLAN),
            ("snp", SNP_RESCUE_PLAN),
            ("classical", CLASSICAL_RESCUE_PLAN),
        ):
            no_drop = [a for a in plan if not a.startswith("(drop")]
            cases.append((variant, plan, ValidationResultStatus.VALID))
            cases.append((variant, no_drop, ValidationResultStatus.INVALID))
        return [
            (*_config(variant, **RESCUE), "\n".join(plan), expected)
            for variant, plan, expected in cases
        ]
