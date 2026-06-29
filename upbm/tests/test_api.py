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

import pytest
from upbm import DomainFactory
from typing import Dict, Any
from upbm.utils import get_reduced_instance_space


@pytest.fixture
def factory():
    return DomainFactory()


def test_generate_instance(factory):
    domain = "matchcellar"
    dom_space = factory.get_domain_parameter_space(domain)
    dom_params = factory.parse_configuration(
        {"version": "1", "variant": "ipc"}, dom_space
    )

    inst_space = factory.get_instance_parameter_space(domain, dom_params)
    inst_params = factory.parse_configuration(
        {"n_matches": "2", "n_fuses": "3"}, inst_space
    )

    problem = factory.generate_instance(domain, dom_params, inst_params)
    assert problem is not None
    assert "instance" in problem.name.lower()


def test_sample_instances(factory):
    domain = "matchcellar"
    dom_space = factory.get_domain_parameter_space(domain)
    dom_params = factory.parse_configuration(
        {"version": "1", "variant": "ipc"}, dom_space
    )
    reducing_dict: Dict[str, Any] = {}
    reducing_dict["n_fuses"] = 1
    reducing_dict["n_matches"] = (5, 10)
    reduced_space = get_reduced_instance_space(
        factory.get_instance_parameter_space(domain, dom_params), reducing_dict
    )
    problems = factory.sample_instances(
        domain, dom_params, n=3, instance_parameter_space=reduced_space
    )
    assert len(problems) == 3
    for p in problems:
        assert p is not None
        assert "instance" in p.name.lower()


def test_generate_dataset(factory, tmp_path):
    dataset_spec = tmp_path / "test_set.yml"
    dataset_spec.write_text(
        """\
domain: matchcellar
params:
  version: 1
  variant: ipc
instances:
  - name: inst1
    params:
      n_matches: 1
      n_fuses: 1
  - name: inst2
    params:
      n_matches: 2
      n_fuses: 2
"""
    )

    instances, _ = factory.generate_dataset(dataset_spec)
    assert len(instances) == 2
    assert instances[0][0] == "inst1"
    assert instances[1][0] == "inst2"
    assert instances[0][1] is not None
    assert instances[1][1] is not None


def test_parse_configuration_unknown_key(factory):
    domain = "matchcellar"
    dom_space = factory.get_domain_parameter_space(domain)
    with pytest.raises(ValueError, match="Unknown parameter"):
        factory.parse_configuration({"nonexistent_param": "42"}, dom_space)
