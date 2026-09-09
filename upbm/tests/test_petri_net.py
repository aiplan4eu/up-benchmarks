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

import tempfile
import warnings
from pathlib import Path

from ConfigSpace import Configuration, ConfigurationSpace, Constant, Integer
from unified_planning.engines.plan_validator import (
    SequentialPlanValidator,
    ValidationResultStatus,
)

from upbm.domains.petri_net import PetriNetGenerator
from upbm.io import Format, dump_instance, parse_plan_string
from upbm.tests.base_domain_test import BaseDomainTest


# How many places each of the three shipped nets has, and how many facts
# describe its structure, read off the dataset files.
IPC_NET_SIZES = {
    0: (26, 36),  # prob06 / prob08
    1: (18, 28),  # prob07
    2: (13, 15),  # prob09 / prob10
}

# The (net, goal_style) pair behind each of the 5 shipped problem families.
IPC_FAMILIES = {
    "prob06": (0, 0),
    "prob07": (1, 0),
    "prob08": (0, 1),
    "prob09": (2, 0),
    "prob10": (2, 1),
}


class TestPetriNet(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "petri-net"

    @property
    def generator(self):
        return PetriNetGenerator

    def _gen(self):
        domain_config = (
            PetriNetGenerator.get_domain_parameter_space().get_default_configuration()
        )
        return domain_config, PetriNetGenerator(domain_config)

    def _config(self, gen, net, goal_style, goal_tokens, goal_amount):
        return Configuration(
            gen.instance_parameter_space,
            {
                "net": net,
                "goal_style": goal_style,
                "goal_tokens": goal_tokens,
                "goal_amount": goal_amount,
            },
        )

    def _get_configs(self):
        domain_config, gen = self._gen()
        # Deliberately NOT an IPC instance: every shipped one asks for at
        # least one token in the goal place, which costs 4 tokens through the
        # funnel. This one only asks for a single token to reach a branch tip,
        # which is a four action plan.
        tiny = self._config(gen, net=2, goal_style=0, goal_tokens=0, goal_amount=1)
        return [(domain_config, tiny)]

    @property
    def plannable(self):
        return self._get_configs()

    @property
    def object_data(self):
        domain_config, instance_config = self._get_configs()[0]
        return [(domain_config, instance_config, [("place", IPC_NET_SIZES[2][0])])]

    @property
    def problem_actions(self):
        domain_config, instance_config = self._get_configs()[0]
        # create, increment and the six fire-* actions; they are lifted, so
        # the count does not depend on the net
        return [(domain_config, instance_config, 8)]

    def test_sequential_plan_validation(self):
        """Walk the funnel net by hand.

        The base class validates with TimeTriggeredPlanValidator, which only
        suits temporal domains; petri-net is instantaneous, so it is checked
        here with the sequential validator instead.

        Putting one token in the goal place costs four tokens: g is fed by
        `(two-to-one d1 d2 g)`, d1 takes one token from a branch tip and d2
        takes one from each of the three tips at once. So four tokens are
        pushed down the branches and then combined, leaving the tips empty.
        """
        domain_config, gen = self._gen()
        problem = gen.get_instance(
            self._config(gen, net=2, goal_style=1, goal_tokens=1, goal_amount=0)
        )
        # send one token from the source down to the tip of one branch
        def to_tip(branch):
            return f"""
            (create s0)
            (fire-one-to-one s0 {branch}1)
            (fire-one-to-one {branch}1 {branch}2)
            (fire-one-to-one {branch}2 {branch}3)
            """

        plan = parse_plan_string(
            problem,
            to_tip("a")
            + to_tip("a")
            + to_tip("b")
            + to_tip("c")
            + """
            (fire-one-to-one a3 d1)
            (fire-three-to-one a3 b3 c3 d2)
            (fire-two-to-one d1 d2 g)
            """,
        )
        with SequentialPlanValidator(problem_kind=problem.kind) as validator:
            res = validator.validate(problem, plan)
            self.assertEqual(res.status, ValidationResultStatus.VALID, f"{res}")

    def test_nets_match_the_ipc_set(self):
        """The three nets are fixed data, so pin their size and their wiring."""
        _, gen = self._gen()
        for net, (n_places, n_facts) in IPC_NET_SIZES.items():
            problem = gen.get_instance(
                self._config(gen, net=net, goal_style=0, goal_tokens=1, goal_amount=0)
            )
            self.assertEqual(len(list(problem.all_objects)), n_places)
            facts = [
                k
                for k, v in problem.explicit_initial_values.items()
                if v.is_bool_constant() and v.bool_constant_value()
            ]
            self.assertEqual(len(facts), n_facts, f"net {net}")
        # spot check the wiring that makes each net what it is: the recycling
        # triangle of net 0, the self doubling place of net 1 and the funnel
        # of net 2
        expectations = {
            0: ["one-to-two(a5, a6, a4)", "three-to-one(a7, b7, c7, g)"],
            1: ["one-to-two(p8, p8, p8)", "two-to-one(p8, q8, g)", "sink(p2)"],
            2: ["three-to-one(a3, b3, c3, d2)", "two-to-one(d1, d2, g)"],
        }
        for net, wanted in expectations.items():
            problem = gen.get_instance(
                self._config(gen, net=net, goal_style=0, goal_tokens=1, goal_amount=0)
            )
            facts = {
                str(k)
                for k, v in problem.explicit_initial_values.items()
                if v.is_bool_constant() and v.bool_constant_value()
            }
            for fact in wanted:
                self.assertIn(fact, facts, f"net {net}")
            self.assertIn("source(s0)", facts, f"net {net}")

    def test_every_place_starts_empty(self):
        """All 20 shipped instances start with every place and the cost at 0."""
        _, gen = self._gen()
        for net in IPC_NET_SIZES:
            problem = gen.get_instance(
                self._config(gen, net=net, goal_style=0, goal_tokens=1, goal_amount=0)
            )
            value = problem.fluent("value")
            for obj in problem.all_objects:
                self.assertEqual(
                    problem.explicit_initial_values[value(obj)].constant_value(), 0
                )
            self.assertEqual(
                problem.explicit_initial_values[
                    problem.fluent("cost")()
                ].constant_value(),
                0,
            )

    def test_goal_shapes_of_the_five_families(self):
        """Each (net, goal_style) pair reproduces one shipped goal shape."""
        _, gen = self._gen()
        expected = {
            # prob06-1
            "prob06": [
                "(3 == value(g))",
                "(value(a4) == 2)",
                "(value(b4) == 2)",
                "(value(c4) == 2)",
            ],
            # prob07-1
            "prob07": [
                "(3 == value(g))",
                "(2 == value(p5))",
                "(2 == value(q5))",
                "(value(p2) == 0)",
                "(value(p3) == 0)",
                "(value(p4) == 0)",
                "(value(q2) == 0)",
                "(value(q3) == 0)",
                "(value(q4) == 0)",
            ],
            # prob08-1, with the amount raised to match the shipped 3
            "prob08": [
                "(3 == value(g))",
                "(3 <= (value(a7) + value(b7) + value(c7)))",
            ],
            # prob09-1 asks for 5 tokens; only the shape is checked here
            "prob09": [
                "(3 == value(g))",
                "(2 == (value(a3) + value(b3) + value(c3)))",
            ],
            # prob10-1, likewise
            "prob10": [
                "(3 == value(g))",
                "(value(a3) == 2)",
                "(value(b3) == 2)",
                "(value(c3) == 2)",
            ],
        }
        for family, (net, goal_style) in IPC_FAMILIES.items():
            amount = 3 if family == "prob08" else 2
            goals = gen.get_goal(
                self._config(
                    gen,
                    net=net,
                    goal_style=goal_style,
                    goal_tokens=3,
                    goal_amount=amount,
                )
            )
            self.assertEqual([str(g) for g in goals], expected[family], family)

    def test_a_net_only_offers_its_own_goal_styles(self):
        """Net 1 ships a single goal shape, so the second one is refused."""
        _, gen = self._gen()
        for net in (0, 2):
            self.assertTrue(
                gen.check_instance_parameters(
                    self._config(
                        gen, net=net, goal_style=1, goal_tokens=1, goal_amount=1
                    )
                )
            )
        rejected = self._config(gen, net=1, goal_style=1, goal_tokens=1, goal_amount=1)
        self.assertFalse(gen.check_instance_parameters(rejected))
        with self.assertRaises(ValueError):
            gen.get_instance(rejected)

    def test_shipped_instances_are_accepted(self):
        """Every (net, goal_style) pair of the IPC set has to be accepted."""
        _, gen = self._gen()
        for family, (net, goal_style) in IPC_FAMILIES.items():
            self.assertTrue(
                gen.check_instance_parameters(
                    self._config(
                        gen,
                        net=net,
                        goal_style=goal_style,
                        goal_tokens=1,
                        goal_amount=1,
                    )
                ),
                f"shipped family rejected: {family}",
            )
        # and the 20 instances are all the valid combinations of a net, one of
        # its goal styles and the token counts the set uses
        space = ConfigurationSpace(
            {
                "net": Integer("net", (0, 2)),
                "goal_style": Integer("goal_style", (0, 1)),
                "goal_tokens": Constant("goal_tokens", 3),
                "goal_amount": Constant("goal_amount", 1),
            }
        )
        configs = list(gen.get_all_instances_configurations(space))
        self.assertEqual(len(configs), 5)

    def test_object_universe_covers_every_net(self):
        """The universe is the union of the places of the nets in the space."""
        _, gen = self._gen()
        names = [o.name for o in gen.object_universe()]
        self.assertEqual(len(names), len(set(names)), "duplicated place")
        # a1, a2 and a3 belong to both net 0 and net 2, so the union is
        # smaller than the sum of the three nets
        self.assertEqual(len(names), 44)
        for place in ("s0", "g", "a8", "p8", "q8", "d1", "d2"):
            self.assertIn(place, names)
        # restricting the space to one net restricts the universe too
        one_net = ConfigurationSpace(
            {
                "net": Constant("net", 2),
                "goal_style": Integer("goal_style", (0, 1)),
                "goal_tokens": Integer("goal_tokens", (0, 10)),
                "goal_amount": Integer("goal_amount", (0, 10)),
            }
        )
        self.assertEqual(len(list(gen.object_universe(one_net))), IPC_NET_SIZES[2][0])

    def test_metric_is_kept_in_every_instance(self):
        for domain_config, instance_config in self._get_configs():
            gen = PetriNetGenerator(domain_config)
            problem = gen.get_instance(instance_config)
            self.assertEqual(len(problem.quality_metrics), 1)
            self.assertIn("cost", str(problem.quality_metrics[0]))

    def test_anml_warns_about_lost_metric(self):
        domain_config, instance_config = self._get_configs()[0]
        gen = PetriNetGenerator(domain_config)
        problem = gen.get_instance(instance_config)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "problem.anml"
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                dump_instance(problem, Format.ANML, out)
            # the warning must not stop the file from being written
            self.assertTrue(out.exists())
            self.assertEqual(len(caught), 1)
            self.assertIn("metric", str(caught[0].message))
