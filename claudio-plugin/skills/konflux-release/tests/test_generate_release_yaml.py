import sys
import yaml
import pytest

from scripts.generate_release_yaml import (
    apply_template_substitutions,
    load_cves_from_file,
    load_release_notes_template,
    generate_prod_release_yaml,
    main,
)

# ── Templates used across tests ───────────────────────────────────────────────

RHAIIS_TEMPLATE = {
    "synopsis": "RHAIIS {version} ({accelerator})",
    "topic": "{accelerator} {version} is now available.",
}

RHELAI_TEMPLATE = {
    "synopsis": "Red Hat Enterprise Linux AI {version}",
    "topic": "Red Hat Enterprise Linux AI {version} is now available.",
}


# ── apply_template_substitutions ──────────────────────────────────────────────

class TestApplyTemplateSubstitutions:
    def test_substitutes_version(self):
        assert apply_template_substitutions("RHAIIS {version}", "3.3.0", "CUDA") == "RHAIIS 3.3.0"

    def test_substitutes_accelerator(self):
        assert apply_template_substitutions("{accelerator} image", "3.3.0", "CUDA") == "CUDA image"

    def test_substitutes_both(self):
        assert apply_template_substitutions("{accelerator} {version}", "3.3.0", "ROCm") == "ROCm 3.3.0"

    def test_recursive_dict(self):
        tmpl = {"synopsis": "{accelerator} {version}", "nested": {"topic": "{version}"}}
        result = apply_template_substitutions(tmpl, "3.3.0", "CUDA")
        assert result == {"synopsis": "CUDA 3.3.0", "nested": {"topic": "3.3.0"}}

    def test_recursive_list(self):
        assert apply_template_substitutions(["{version}", "{accelerator}"], "3.3.0", "ROCm") == ["3.3.0", "ROCm"]

    def test_non_string_values_passthrough(self):
        tmpl = {"count": 42, "flag": True, "nothing": None}
        assert apply_template_substitutions(tmpl, "3.3.0", "CUDA") == tmpl

    def test_empty_accelerator_ignored_when_not_in_template(self):
        # RHELAI templates only use {version} — empty accelerator must not break anything
        assert apply_template_substitutions("RHELAI {version}", "3.3.0", "") == "RHELAI 3.3.0"

    def test_empty_accelerator_substitutes_empty_string(self):
        assert apply_template_substitutions("{accelerator} {version}", "3.3.0", "") == " 3.3.0"


# ── load_cves_from_file ────────────────────────────────────────────────────────

class TestLoadCvesFromFile:
    def test_loads_cves(self, tmp_path):
        f = tmp_path / "cves.txt"
        f.write_text("CVE-2024-1234\nCVE-2024-5678\n")
        assert load_cves_from_file(str(f)) == ["CVE-2024-1234", "CVE-2024-5678"]

    def test_skips_blank_lines(self, tmp_path):
        f = tmp_path / "cves.txt"
        f.write_text("\nCVE-2024-1234\n\nCVE-2024-5678\n")
        assert load_cves_from_file(str(f)) == ["CVE-2024-1234", "CVE-2024-5678"]

    def test_skips_comments(self, tmp_path):
        f = tmp_path / "cves.txt"
        f.write_text("# comment\nCVE-2024-1234\n# another\nCVE-2024-5678\n")
        assert load_cves_from_file(str(f)) == ["CVE-2024-1234", "CVE-2024-5678"]

    def test_strips_whitespace(self, tmp_path):
        f = tmp_path / "cves.txt"
        f.write_text("  CVE-2024-1234  \n")
        assert load_cves_from_file(str(f)) == ["CVE-2024-1234"]

    def test_exits_on_missing_file(self):
        with pytest.raises(SystemExit):
            load_cves_from_file("/nonexistent/cves.txt")


# ── load_release_notes_template ───────────────────────────────────────────────

class TestLoadReleaseNotesTemplate:
    def test_loads_valid_yaml(self, tmp_path):
        f = tmp_path / "template.yaml"
        f.write_text("synopsis: test\ntopic: foo\n")
        assert load_release_notes_template(str(f)) == {"synopsis": "test", "topic": "foo"}

    def test_exits_on_missing_file(self):
        with pytest.raises(SystemExit):
            load_release_notes_template("/nonexistent/template.yaml")

    def test_exits_on_invalid_yaml(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text("key: [unclosed")
        with pytest.raises(SystemExit):
            load_release_notes_template(str(f))


# ── generate_prod_release_yaml ────────────────────────────────────────────────

class TestGenerateProdReleaseYaml:
    def _call(self, **overrides):
        defaults = dict(
            component_name="my-comp",
            version="3.3.0",
            snapshot="snap-abc123",
            release_plan="my-plan-prod",
            release_name="my-comp-3-3-0-prod-1",
            accelerator="CUDA",
            namespace="my-namespace",
            release_notes_template=RHAIIS_TEMPLATE.copy(),
            release_type="RHEA",
            cves_file=None,
            grace_period=30,
        )
        defaults.update(overrides)
        return generate_prod_release_yaml(**defaults)

    def test_output_structure(self):
        result = self._call()
        assert result["apiVersion"] == "appstudio.redhat.com/v1alpha1"
        assert result["kind"] == "Release"
        assert result["metadata"]["name"] == "my-comp-3-3-0-prod-1"
        assert result["metadata"]["namespace"] == "my-namespace"
        assert result["spec"]["releasePlan"] == "my-plan-prod"
        assert result["spec"]["snapshot"] == "snap-abc123"
        assert result["spec"]["gracePeriodDays"] == 30

    def test_rhea_sets_type(self):
        assert self._call(release_type="RHEA")["spec"]["data"]["releaseNotes"]["type"] == "RHEA"

    def test_rhsa_sets_type(self):
        assert self._call(release_type="RHSA")["spec"]["data"]["releaseNotes"]["type"] == "RHSA"

    def test_rhsa_without_cves_file_has_no_cves_key(self):
        assert "cves" not in self._call(release_type="RHSA", cves_file=None)["spec"]["data"]["releaseNotes"]

    def test_rhsa_with_cves_file(self, tmp_path):
        cve_file = tmp_path / "cves.txt"
        cve_file.write_text("CVE-2024-1234\nCVE-2024-5678\n")
        cves = self._call(release_type="RHSA", cves_file=str(cve_file))["spec"]["data"]["releaseNotes"]["cves"]
        assert cves == [
            {"key": "CVE-2024-1234", "component": "my-comp-3-3-0"},
            {"key": "CVE-2024-5678", "component": "my-comp-3-3-0"},
        ]

    def test_template_substitution_applied(self):
        notes = self._call(version="3.3.0", accelerator="CUDA")["spec"]["data"]["releaseNotes"]
        assert notes["synopsis"] == "RHAIIS 3.3.0 (CUDA)"
        assert notes["topic"] == "CUDA 3.3.0 is now available."

    def test_grace_period(self):
        assert self._call(grace_period=365)["spec"]["gracePeriodDays"] == 365

    def test_rhelai_style_no_component_no_accelerator(self):
        # RHELAI: full-application release, template only uses {version}
        result = generate_prod_release_yaml(
            component_name=None,
            version="3.3.0",
            snapshot="rhelai-bootc-snap-abc",
            release_plan="bootc-containers-full-prod",
            release_name="rhelai-containers-3-3-0-prod-1",
            accelerator="",
            namespace="rhel-ai-tenant",
            release_notes_template=RHELAI_TEMPLATE.copy(),
            release_type="RHEA",
            cves_file=None,
            grace_period=30,
        )
        notes = result["spec"]["data"]["releaseNotes"]
        assert notes["synopsis"] == "Red Hat Enterprise Linux AI 3.3.0"
        assert notes["topic"] == "Red Hat Enterprise Linux AI 3.3.0 is now available."
        assert result["spec"]["releasePlan"] == "bootc-containers-full-prod"


# ── main() / CLI ──────────────────────────────────────────────────────────────

class TestMain:
    def _base_argv(self, tmp_path, template_content="synopsis: '{version}'\n"):
        tmpl = tmp_path / "template.yaml"
        tmpl.write_text(template_content)
        return [
            "prog",
            "--version", "3.3.0",
            "--snapshot", "snap-1",
            "--release-plan", "my-plan",
            "--release-name", "my-release-1",
            "--namespace", "ns",
            "--release-notes-template", str(tmpl),
        ]

    def test_stdout_output(self, tmp_path, monkeypatch, capsys):
        argv = self._base_argv(tmp_path, "synopsis: 'RHAIIS {version} ({accelerator})'\n")
        argv += ["--component", "my-comp", "--accelerator", "CUDA"]
        monkeypatch.setattr(sys, "argv", argv)
        main()
        data = yaml.safe_load(capsys.readouterr().out)
        assert data["kind"] == "Release"
        assert data["metadata"]["name"] == "my-release-1"

    def test_file_output_creates_dirs(self, tmp_path, monkeypatch):
        out_file = tmp_path / "out" / "release.yaml"
        argv = self._base_argv(tmp_path) + ["--output", str(out_file)]
        monkeypatch.setattr(sys, "argv", argv)
        main()
        assert out_file.exists()
        assert yaml.safe_load(out_file.read_text())["kind"] == "Release"

    def test_rhelai_style_no_component_no_accelerator(self, tmp_path, monkeypatch, capsys):
        # Neither --component nor --accelerator provided — must succeed for RHEA
        argv = self._base_argv(tmp_path, "synopsis: 'RHELAI {version}'\n")
        monkeypatch.setattr(sys, "argv", argv)
        main()
        data = yaml.safe_load(capsys.readouterr().out)
        assert data["spec"]["data"]["releaseNotes"]["synopsis"] == "RHELAI 3.3.0"

    def test_rhsa_without_component_and_cves_file_fails(self, tmp_path, monkeypatch):
        cve_file = tmp_path / "cves.txt"
        cve_file.write_text("CVE-2024-1234\n")
        argv = self._base_argv(tmp_path) + ["--release-type", "RHSA", "--cves-file", str(cve_file)]
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code != 0

    def test_missing_required_arg_fails(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["prog", "--version", "3.3.0"])
        with pytest.raises(SystemExit):
            main()
