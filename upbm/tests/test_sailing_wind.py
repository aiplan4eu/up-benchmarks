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

from upbm.domains.sailing_wind import SailingWindGenerator
from upbm.tests.base_domain_test import BaseDomainTest


def _config(variant, **params):
    """The domain configuration of `variant` and an instance configuration of it."""
    domain_space = SailingWindGenerator.get_domain_parameter_space()
    domain_config = Configuration(domain_space, {"version": 1, "variant": variant})
    space = SailingWindGenerator(domain_config).instance_parameter_space
    return domain_config, Configuration(space, params)


def _moves(*angles):
    return [f"(move_{angle} b0)" for angle in angles]


class TestSailingWind(BaseDomainTest):
    __test__ = True

    @property
    def domain_name(self):
        return "sailing-wind"

    @property
    def generator(self):
        return SailingWindGenerator

    def _get_configs(self):
        """One instance per layout."""
        return [
            _config("line", step=0, inertia=50),
            _config("circle", n_people=2, skip=2, gap=1, inertia=0),
            _config("random", n_people=1, max_distance=16, seed=3, inertia=50),
        ]

    @property
    def plannable(self):
        # Even the smaller instances are too hard for unit tests
        return []

    @property
    def object_data(self):
        line, circle, drawn = self._get_configs()
        return [
            (*line, [("boat", 1), ("person", 1)]),
            (*circle, [("boat", 1), ("person", 2)]),
            (*drawn, [("boat", 1), ("person", 1)]),
        ]

    @property
    def problem_actions(self):
        return [(*config, 25) for config in self._get_configs()]

    @property
    def validation_cases(self):
        line, circle, drawn = self._get_configs()

        line_rescue = _moves(15) * 5 + _moves(0) + ["(save_person b0 p0)"]

        east = (
            _moves(15, 30, 45, 60, 75, 90)
            + _moves(90) * 63
            + _moves(75, 60, 45, 30, 15, 0)
            + ["(save_person b0 p0)"]
        )
        south_west = (
            _moves(345, 330, 315, 300, 285, 270, 255, 240, 225)
            + _moves(225) * 106
            + _moves(240, 255, 270, 285, 300, 315, 330, 345, 0)
            + ["(save_person b0 p1)"]
        )

        climb = _moves(15) * 10

        cases = [
            (*line, line_rescue, ValidationResultStatus.VALID),
            (*line, ["(save_person b0 p0)"], ValidationResultStatus.INVALID),
            (
                *line,
                _moves(15) * 5 + ["(save_person b0 p0)"],
                ValidationResultStatus.INVALID,
            ),
            (*line, [], ValidationResultStatus.INVALID),
            (*circle, east + south_west, ValidationResultStatus.VALID),
            (*circle, east, ValidationResultStatus.INVALID),
            (
                *drawn,
                climb + _moves(0) + ["(save_person b0 p0)"],
                ValidationResultStatus.VALID,
            ),
            (*drawn, climb + ["(save_person b0 p0)"], ValidationResultStatus.INVALID),
            (
                *drawn,
                _moves(15) * 3 + _moves(0) * 4 + ["(save_person b0 p0)"],
                ValidationResultStatus.INVALID,
            ),
        ]
        return [
            (domain_config, instance_config, "\n".join(plan), expected)
            for domain_config, instance_config, plan, expected in cases
        ]
