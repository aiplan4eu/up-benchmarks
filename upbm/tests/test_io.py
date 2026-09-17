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

"""Tests for the output formats, independent of any one domain.

ANML has no syntax for plan quality metrics, so a problem that defines one
loses it when it is written that way. `warn_if_metric_lost` says so rather than
letting it happen quietly. That behaviour belongs to `upbm.io`, not to any
domain, so it is tested once here.

Two domains are used as fixtures, the way `test_api.py` uses matchcellar to
check the generic parts of the factory: `coins` because it defines a metric,
and `matchcellar` because it does not.
"""

import warnings

import pytest

from upbm import DomainFactory
from upbm.io import Format, dump_instance, print_instance


@pytest.fixture
def factory():
    return DomainFactory()


def _instance(factory, domain, **instance_params):
    dom_space = factory.get_domain_parameter_space(domain)
    dom_params = factory.parse_configuration({"variant": "ipc"}, dom_space)
    inst_space = factory.get_instance_parameter_space(domain, dom_params)
    inst_params = factory.parse_configuration(instance_params, inst_space)
    return factory.generate_instance(domain, dom_params, inst_params)


def with_metric(factory):
    """A problem that defines a quality metric."""
    problem = _instance(factory, "coins", n_coins=5, target=5)
    assert problem.quality_metrics, "coins is expected to define a metric"
    return problem


def without_metric(factory):
    """A problem that defines none."""
    problem = _instance(factory, "matchcellar", n_matches=2, n_fuses=2)
    assert not problem.quality_metrics, "matchcellar is expected to define no metric"
    return problem


def test_anml_warns_about_the_lost_metric(factory, tmp_path):
    problem = with_metric(factory)
    out = tmp_path / "problem.anml"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        dump_instance(problem, Format.ANML, out)

    assert len(caught) == 1
    assert "metric" in str(caught[0].message)
    # the warning must not stop the file from being written
    assert out.exists()
    assert out.stat().st_size > 0


def test_printing_anml_warns_too(factory, capsys):
    """print_instance takes the same path as dump_instance."""
    problem = with_metric(factory)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        print_instance(problem, Format.ANML)

    assert len(caught) == 1
    assert "metric" in str(caught[0].message)
    # and the problem still reaches stdout
    assert capsys.readouterr().out.strip()


def test_pddl_keeps_the_metric_and_stays_quiet(factory, tmp_path):
    """Nothing is lost in PDDL, so there is nothing to warn about."""
    problem = with_metric(factory)
    prob_file, dom_file = tmp_path / "problem.pddl", tmp_path / "domain.pddl"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        dump_instance(problem, Format.PDDL, prob_file, dom_file)

    assert caught == []
    assert ":metric" in prob_file.read_text()


def test_anml_stays_quiet_without_a_metric(factory, tmp_path):
    problem = without_metric(factory)
    out = tmp_path / "problem.anml"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        dump_instance(problem, Format.ANML, out)

    assert caught == []
    assert out.exists()
