import pytest
from upbm import DomainFactory


@pytest.fixture
def factory():
    return DomainFactory()


def test_generate_instance(factory):
    domain = "matchcellar"
    dom_space = factory.get_domain_parameter_space(domain)
    dom_params = factory.parse_configuration({"version": "1", "variant": "ipc"}, dom_space)

    inst_space = factory.get_instance_parameter_space(domain, dom_params)
    inst_params = factory.parse_configuration({"n_matches": "2", "n_fuses": "3"}, inst_space)

    problem = factory.generate_instance(domain, dom_params, inst_params)
    assert problem is not None
    assert "instance" in problem.name.lower()


def test_sample_instances(factory):
    domain = "matchcellar"
    dom_space = factory.get_domain_parameter_space(domain)
    dom_params = factory.parse_configuration({"version": "1", "variant": "ipc"}, dom_space)

    problems = factory.sample_instances(domain, dom_params, n=3, fixed_instance_params={"n_matches": "1"})
    assert len(problems) == 3
    for p in problems:
        assert p is not None
        assert "instance" in p.name.lower()


def test_generate_dataset(factory, tmp_path):
    dataset_spec = tmp_path / "test_set.yml"
    dataset_spec.write_text("""\
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
""")

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
