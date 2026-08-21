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
from upbm.domains.expedition.expedition import (
    DEPOT_SUPPLIES,
    N_SLEDS,
    SLED_CAPACITY,
    SLED_INITIAL_SUPPLIES,
)
from upbm.io import parse_plan_string
from upbm.tests.base_domain_test import BaseDomainTest
from upbm.utils import get_reduced_instance_space


def _domain_config():
    return ExpeditionGenerator.get_domain_parameter_space().get_default_configuration()


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
        space = ExpeditionGenerator(config).instance_parameter_space
        return [
            # the shortest chain there can be: one move each and they are done
            (config, Configuration(space, {"n_waypoints": 2, "n_chains": 1})),
            # short enough to plan, long enough to need the depot
            (config, Configuration(space, {"n_waypoints": 3, "n_chains": 1})),
            # the two chain half of the set, one sled and one depot each
            (config, Configuration(space, {"n_waypoints": 3, "n_chains": 2})),
        ]

    @property
    def plannable(self):
        # all three are tiny; the IPC chains of 6+ need a lot of ferrying and
        # are far too slow for a unit test
        return self._get_configs()

    @property
    def object_data(self):
        tiny, short, two_chains = self._get_configs()
        return [
            (*tiny, [("sled", N_SLEDS), ("waypoint", 2)]),
            (*short, [("sled", N_SLEDS), ("waypoint", 3)]),
            # two chains of three waypoints
            (*two_chains, [("sled", N_SLEDS), ("waypoint", 6)]),
        ]

    @property
    def problem_actions(self):
        # move_forwards, move_backwards, store_supplies, retrieve_supplies
        return [(*config, 4) for config in self._get_configs()]

    def test_chain_is_wired_end_to_end(self):
        """is_next links each waypoint to the next one, and nothing else."""
        domain_config, instance_config = self._get_configs()[1]
        gen = ExpeditionGenerator(domain_config)
        problem = gen.get_instance(instance_config)
        is_next = problem.fluent("is_next")

        links = {
            (f.args[0].object().name, f.args[1].object().name)
            for f, v in problem.explicit_initial_values.items()
            if f.fluent() == is_next and v.bool_constant_value()
        }
        self.assertEqual(links, {("wa0", "wa1"), ("wa1", "wa2")})

    def test_only_the_chain_start_is_a_depot(self):
        for domain_config, instance_config in self._get_configs():
            gen = ExpeditionGenerator(domain_config)
            problem = gen.get_instance(instance_config)
            supplies = problem.fluent("waypoint_supplies")
            for waypoint in problem.objects(problem.user_type("waypoint")):
                value = problem.initial_value(supplies(waypoint)).constant_value()
                expected = DEPOT_SUPPLIES if waypoint.name.endswith("0") else 0
                self.assertEqual(value, expected, f"{waypoint.name} has {value}")

    def test_sleds_start_together_or_apart(self):
        """One chain means both sleds share it, two means one each."""
        _, shared, separate = self._get_configs()
        gen = ExpeditionGenerator(_domain_config())

        shared_problem = gen.get_instance(shared[1])
        at = shared_problem.fluent("at")
        self.assertTrue(
            shared_problem.initial_value(
                at(shared_problem.object("s0"), shared_problem.object("wa0"))
            ).bool_constant_value()
        )
        self.assertTrue(
            shared_problem.initial_value(
                at(shared_problem.object("s1"), shared_problem.object("wa0"))
            ).bool_constant_value()
        )
        self.assertEqual(
            {str(g) for g in shared_problem.goals},
            {"at(s0, wa2)", "at(s1, wa2)"},
        )

        separate_problem = gen.get_instance(separate[1])
        at = separate_problem.fluent("at")
        self.assertTrue(
            separate_problem.initial_value(
                at(separate_problem.object("s1"), separate_problem.object("wb0"))
            ).bool_constant_value()
        )
        self.assertEqual(
            {str(g) for g in separate_problem.goals},
            {"at(s0, wa2)", "at(s1, wb2)"},
        )

    def test_sled_capacity_and_supplies(self):
        domain_config, instance_config = self._get_configs()[0]
        gen = ExpeditionGenerator(domain_config)
        problem = gen.get_instance(instance_config)
        capacity = problem.fluent("sled_capacity")
        supplies = problem.fluent("sled_supplies")
        for sled in problem.objects(problem.user_type("sled")):
            self.assertEqual(
                problem.initial_value(capacity(sled)).constant_value(), SLED_CAPACITY
            )
            self.assertEqual(
                problem.initial_value(supplies(sled)).constant_value(),
                SLED_INITIAL_SUPPLIES,
            )

    def test_no_quality_metric(self):
        # the shipped instances define no :metric
        for domain_config, instance_config in self._get_configs():
            gen = ExpeditionGenerator(domain_config)
            problem = gen.get_instance(instance_config)
            self.assertEqual(list(problem.quality_metrics), [])

    def test_object_universe_is_bounded_by_the_space(self):
        gen = ExpeditionGenerator(_domain_config())
        reduced = get_reduced_instance_space(
            gen.instance_parameter_space, {"n_waypoints": 4, "n_chains": 2}
        )
        names = sorted(o.name for o in gen.object_universe(reduced))
        self.assertEqual(
            names,
            ["s0", "s1"] + [f"wa{i}" for i in range(4)] + [f"wb{i}" for i in range(4)],
        )

    # NOTE the validation cases of the base class use the temporal plan
    # validator, while expedition is an instantaneous domain, so the sequential
    # plans are validated here instead.
    def test_sequential_validation(self):
        domain_config, instance_config = self._get_configs()[1]
        gen = ExpeditionGenerator(domain_config)
        problem = gen.get_instance(instance_config)

        # A chain of three waypoints is two moves, but a sled only starts with
        # one supply, so it has to top up from the depot at wa0 first.
        def trek(sled):
            return [
                f"(retrieve_supplies {sled} wa0)",
                f"(move_forwards {sled} wa0 wa1)",
                f"(move_forwards {sled} wa1 wa2)",
            ]

        for plan_str, expected in [
            ("\n".join(trek("s0") + trek("s1")), ValidationResultStatus.VALID),
            # without topping up, a sled runs out after the first move
            (
                "\n".join(["(move_forwards s0 wa0 wa1)", "(move_forwards s0 wa1 wa2)"]),
                ValidationResultStatus.INVALID,
            ),
            # only one sled arriving does not satisfy the goal
            ("\n".join(trek("s0")), ValidationResultStatus.INVALID),
            ("", ValidationResultStatus.INVALID),
        ]:
            plan = parse_plan_string(problem, plan_str)
            with SequentialPlanValidator() as validator:
                v_res = validator.validate(problem, plan)
                self.assertEqual(v_res.status, expected, f"bad res:\n{v_res}")

    def test_supplies_can_be_ferried_forward(self):
        """A sled can cache supplies at a waypoint for the other one to use."""
        domain_config, instance_config = self._get_configs()[1]
        gen = ExpeditionGenerator(domain_config)
        problem = gen.get_instance(instance_config)

        # s0 carries supplies up to wa1 and drops one there, then both sleds
        # finish the trip, with s1 picking the cached supply back up at wa1.
        plan_str = "\n".join(
            [
                "(retrieve_supplies s0 wa0)",
                "(retrieve_supplies s0 wa0)",
                "(move_forwards s0 wa0 wa1)",
                "(store_supplies s0 wa1)",
                "(move_forwards s0 wa1 wa2)",
                "(move_forwards s1 wa0 wa1)",
                "(retrieve_supplies s1 wa1)",
                "(move_forwards s1 wa1 wa2)",
            ]
        )
        plan = parse_plan_string(problem, plan_str)
        with SequentialPlanValidator() as validator:
            v_res = validator.validate(problem, plan)
            self.assertEqual(v_res.status, ValidationResultStatus.VALID, f"{v_res}")
