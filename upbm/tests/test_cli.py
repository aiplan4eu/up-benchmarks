import subprocess
import sys


def run_cli(args):
    """Utility to run the CLI and return the result."""
    return subprocess.run(
        [sys.executable, "main.py"] + args, capture_output=True, text=True
    )


def test_cli_help():
    result = run_cli([])
    assert result.returncode == 0
    assert "Available commands" in result.stdout


def test_cli_domains():
    result = run_cli(["domains"])
    assert result.returncode == 0
    assert "matchcellar" in result.stdout


def test_cli_domain_params():
    result = run_cli(["domain-params", "matchcellar"])
    assert result.returncode == 0
    # Check for the table structure
    assert "+" in result.stdout
    assert "|" in result.stdout
    assert "Parameter" in result.stdout
    assert "Type" in result.stdout
    assert "Values/Range" in result.stdout
    assert "Default" in result.stdout
    # Check for specific parameters
    assert "variant" in result.stdout
    assert "Categorical" in result.stdout
    assert "{ipc, variable_duration, long_short_fuse}" in result.stdout


def test_cli_instance_params():
    result = run_cli(
        ["instance-params", "matchcellar", "-d", "version", "1", "-d", "variant", "ipc"]
    )
    assert result.returncode == 0
    assert "Parameter" in result.stdout
    assert "n_matches" in result.stdout
    assert "UniformInteger" in result.stdout


def test_cli_mkinstance_stdout():
    # Test mkinstance printing to stdout
    result = run_cli(
        [
            "mkinstance",
            "matchcellar",
            "-d",
            "version",
            "1",
            "-d",
            "variant",
            "ipc",
            "-p",
            "n_matches",
            "1",
            "-p",
            "n_fuses",
            "1",
            "--format",
            "pddl",
        ]
    )
    assert result.returncode == 0
    assert "(define (domain matchcellar" in result.stdout
    assert "(define (problem matchcellar" in result.stdout


def test_cli_mkinstance_file(tmp_path):
    # Test mkinstance writing to files
    prob_file = tmp_path / "prob.pddl"
    dom_file = tmp_path / "dom.pddl"
    result = run_cli(
        [
            "mkinstance",
            "matchcellar",
            "-d",
            "version",
            "1",
            "-d",
            "variant",
            "ipc",
            "-p",
            "n_matches",
            "1",
            "-p",
            "n_fuses",
            "1",
            "-D",
            str(dom_file),
            "-o",
            str(prob_file),
            "--format",
            "pddl",
        ]
    )
    assert result.returncode == 0
    assert prob_file.exists()
    assert dom_file.exists()
    assert "matchcellar" in dom_file.read_text()
    assert "matchcellar" in prob_file.read_text()


def test_cli_sample(tmp_path):
    # Test sample command
    out_folder = tmp_path / "out"
    result = run_cli(
        [
            "sample",
            "matchcellar",
            "2",
            "-d",
            "version",
            "1",
            "-d",
            "variant",
            "ipc",
            "-p",
            "n_fuses",
            "1",
            "-r",
            "n_matches",
            "1",
            "4",
            "-o",
            str(out_folder),
            "--format",
            "pddl",
        ]
    )
    assert result.returncode == 0
    assert out_folder.exists()
    # Check if files were generated (problem_1.pddl, domain_1.pddl, etc.)
    files = list(out_folder.glob("*.pddl"))
    assert len(files) == 4  # 2 domains + 2 problems
