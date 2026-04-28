from pathlib import Path
from upbm.factory import DomainFactory
from upbm.generator import Generator


class DummyDomainGenerator(Generator):
    # Dummy mock
    pass


def test_manual_registration():
    factory = DomainFactory()
    factory.register("my_dummy", DummyDomainGenerator)

    gen = factory["my_dummy"]
    assert gen is DummyDomainGenerator


def test_independent_factory_instances():
    """Each DomainFactory() is independent; registrations don't bleed across instances."""
    factory_a = DomainFactory()
    factory_b = DomainFactory()
    factory_a.register("only_in_a", DummyDomainGenerator)

    assert factory_a["only_in_a"] is DummyDomainGenerator
    domains_b = factory_b.get_registered_domains()
    assert "only_in_a" not in domains_b


def test_automatic_plugins_loading(tmp_path, monkeypatch):
    # Create synthetic plugin python module
    plugin_module_dir = tmp_path / "plugins_dummy"
    plugin_module_dir.mkdir()
    (plugin_module_dir / "__init__.py").write_text("")
    (plugin_module_dir / "my_plugin.py").write_text(
        """\
from upbm.generator import Generator
class CustomTestGenerator(Generator):
    pass
"""
    )

    import sys

    sys.path.insert(0, str(tmp_path))
    monkeypatch.chdir(tmp_path)

    upbm_file = tmp_path / ".upbm"
    upbm_file.write_text(
        """\
plugins:
  custom_yaml_domain: "plugins_dummy.my_plugin:CustomTestGenerator"
"""
    )

    # Construction auto-loads plugins (including the one in cwd/.upbm)
    factory = DomainFactory()

    custom_gen = factory["custom_yaml_domain"]
    assert custom_gen.__name__ == "CustomTestGenerator"

    sys.path.remove(str(tmp_path))


def test_reload_plugins(tmp_path, monkeypatch):
    """reload_plugins() picks up plugins added after initial construction."""
    plugin_module_dir = tmp_path / "plugins_reload"
    plugin_module_dir.mkdir()
    (plugin_module_dir / "__init__.py").write_text("")
    (plugin_module_dir / "late_plugin.py").write_text(
        """\
from upbm.generator import Generator
class LateGenerator(Generator):
    pass
"""
    )

    import sys

    sys.path.insert(0, str(tmp_path))
    monkeypatch.chdir(tmp_path)

    # Construct before the .upbm file exists
    factory = DomainFactory()
    assert "late_domain" not in factory.get_registered_domains()

    # Now write the config and reload
    (tmp_path / ".upbm").write_text(
        """\
plugins:
  late_domain: "plugins_reload.late_plugin:LateGenerator"
"""
    )
    factory.reload_plugins()

    assert "late_domain" in factory.get_registered_domains()
    assert factory["late_domain"].__name__ == "LateGenerator"

    sys.path.remove(str(tmp_path))
