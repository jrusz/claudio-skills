---
name: konflux-release
description: Create production releases on the Konflux platform. Handles the complete stage-to-production release workflow including discovering stage releases, generating production release YAMLs with release notes, and preparing them for review. Supports manual mode and config-driven mode with an external product config directory.
allowed-tools: Bash(*/konflux-release/scripts/generate_release_yaml.py *),Bash(kubectl get *),Bash(skopeo inspect *),Bash(glab api --method GET *),Write(*RELEASE_SUMMARY*)
---

# Konflux Release

## Overview

Konflux is an open source build and release platform based on OpenShift and Tekton. This skill handles the stage-to-production release workflow: discovering stage releases by commit SHA, generating production release YAMLs with release notes, and preparing them for human review.

The skill generates release YAML files and a summary document. It does NOT apply releases to the cluster -- application of release YAMLs is handled separately through manual review or CI pipelines.

The skill operates in two modes:

- **Manual mode** - provide all parameters directly (namespace, release plans, templates, etc.). Output files are written to a local directory.
- **Config-driven mode** - read product configuration from an external config directory added as a working directory. When a product configs repo is present, its CLAUDE.md provides all product-specific context including where to find component definitions, release plans, release notes templates, and where to store outputs.

**Prerequisites:** `kubectl`, `python3`, `jq`, and optionally `glab` and `skopeo`. These are expected to be pre-installed. Do NOT check or install dependencies upfront — just run the commands and scripts directly. If something fails due to a missing dependency, then install it using the scripts in `tools/`.

**Scripts:**
This skill includes helper scripts in `scripts/` directory.

## Core Concepts

- **Release** - a deployment of a specific snapshot to an environment
- **Snapshot** - a point-in-time reference to built container images
- **ReleasePlan** - defines how and where releases are deployed
- **Application** - group of related components
- **Component** - individual buildable/deployable unit

## Script Execution Requirements

1. **Single-line commands only** - NO line breaks or backslash continuations
2. **DO NOT change directory** - execute scripts using their full absolute path
3. **Full path required** - the script must be invoked with its full filesystem path, not a relative path
4. **One tool call per component** - each component must be handled with a separate tool call. Do NOT use shell loops (`for`, `while`), background processes (`&`), or subshells to batch multiple components into a single command

**Correct execution:**
```bash
/full/path/to/konflux-release/scripts/generate_release_yaml.py --component foo --version 1.0 --snapshot bar --release-plan prod --release-name foo-1-0-prod-1 --accelerator Variant --namespace ns --release-notes-template /path/to/template.yaml --release-type RHEA --output /path/to/out/foo.yaml
```

**Incorrect execution:**
```bash
# DON'T - relative path (won't resolve)
scripts/generate_release_yaml.py ...

# DON'T - changing directory first
cd scripts && ./generate_release_yaml.py ...

# DON'T - line breaks
/path/to/generate_release_yaml.py \
  --component foo \
  --version 1.0

# DON'T - shell loops or background processes
for comp in foo bar baz; do /path/to/generate_release_yaml.py --component $comp ...; done
/path/to/generate_release_yaml.py --component foo ... &
/path/to/generate_release_yaml.py --component bar ... &
wait
```

**Permission pattern:**
- `*/konflux-release/scripts/generate_release_yaml.py *`

This pattern matches the script in any user directory or plugin cache location.

## Release Workflow

### Stage-to-Production Pattern

```
1. Code merged -> CI builds -> Stage Release created
2. Stage Release succeeds -> Snapshot captured (references built images)
3. Production Release YAML generated -> References same Snapshot (same images)
4. Release YAMLs reviewed and applied (manually or via CI)
```

Key principle: stage and production releases reference the same Snapshot because it points to the same built container images.

### Step 1: Resolve Input to Commit SHA

Three options depending on what the user provides:

**Option A - Direct SHA:** User already has the full 40-character commit SHA. No resolution needed.

**Option B - Git tag via glab:**
```bash
glab api --method GET "projects/<url-encoded-project>/repository/commits/<tag>" | jq -r '.id'
```

**Option C - Image URL via skopeo:** Extract the commit SHA from container image labels:
```bash
skopeo inspect --no-tags docker://<image-url> | jq -r '.Labels["vcs-ref"]'
```

### Step 2: Find Stage Releases by SHA

Query releases using the commit SHA label:
```bash
kubectl get releases -n <namespace> -l "pac.test.appstudio.openshift.io/sha=<full-40-char-sha>"
```

Use the full 40-character SHA. Short SHAs won't match labels.

### Step 3: Detect Versioned vs Non-Versioned Releases

Check the `appstudio.openshift.io/application` label on the releases to determine the application name. Some applications use versioned release plans (with version suffix) while others use a single unversioned plan.

```bash
kubectl get releases -n <namespace> -l "pac.test.appstudio.openshift.io/sha=<sha>" -o jsonpath='{.items[0].metadata.labels.appstudio\.openshift\.io/application}'
```

### Step 4: Filter to Successful Releases

Check that each stage release has completed successfully:

```bash
kubectl get releases -n <namespace> -l "pac.test.appstudio.openshift.io/sha=<sha>" -o json | jq '[.items[] | select(.status.conditions[]? | select(.type == "Released" and .status == "True")) | {name: .metadata.name, component: .metadata.labels["appstudio.openshift.io/component"], snapshot: .spec.snapshot, releasePlan: .spec.releasePlan}]'
```

- Only proceed with releases where `.status.conditions[type=Released].status = "True"`
- Report any failed releases to the user
- Do NOT generate production YAMLs for failed stage releases

### Step 5: Determine Component Properties

For each successful stage release, extract:

- **Component name:** `.metadata.labels["appstudio.openshift.io/component"]`
- **Snapshot name:** `.spec.snapshot`
- **Stage ReleasePlan:** `.spec.releasePlan`

Then determine:

- **Tech preview status** - from product config or user input
- **Production ReleasePlan name** - derive from stage plan naming convention
- **Release notes template** - select appropriate template based on component type and tech preview status
- **Variant/accelerator display name** - derive from component name

### Step 6: Auto-Increment Release Version

Query existing production releases to determine the next sequence number:

```bash
kubectl get releases -n <namespace> --sort-by=.metadata.creationTimestamp -o json | jq '[.items[] | select(.metadata.name | startswith("<component>-<version-dashed>-prod-"))] | length'
```

Use length + 1 as the next sequence number for the release name.

### Step 7: Generate Production Release YAMLs

The script automatically creates the output directory. Use the provided script for each component (full path, single line):

```bash
/full/path/to/konflux-release/scripts/generate_release_yaml.py --component <component-name> --version <version> --snapshot <snapshot-name> --release-plan <prod-release-plan> --release-name <release-name> --accelerator <accelerator> --namespace <namespace> --release-notes-template <template-path> --release-type <RHEA|RHSA> --output /path/to/output/<component>-prod.yaml
```

**Required parameters:**
- `--component` - component name
- `--version` - semantic version
- `--snapshot` - snapshot name from the successful stage release
- `--release-plan` - production release plan name
- `--release-name` - unique release name (see naming conventions)
- `--accelerator` - variant/accelerator type for template substitution
- `--namespace` - Kubernetes namespace
- `--release-notes-template` - path to release notes YAML template
- `--release-type` - RHEA (default) or RHSA
- `--output` - output file path

**Optional parameters:**
- `--cves-file` - path to CVE list file (required for RHSA releases)
- `--grace-period` - grace period in days (default: 30)

### Step 8: Generate Release Summary

Create a summary document that includes:
- Release date
- Git commit SHA and source URL
- Component status table (component name, status, release name, release plan)
- Stage release information
- Generated YAML filenames
- Links to Konflux UI for monitoring (if available)

### Step 9: Deliver for Review

The generated release YAMLs and summary are NOT applied directly to the cluster.

**Config-driven mode:** Follow the config repo's CLAUDE.md instructions for where to store output files. Commit the generated files and open a merge request against the config repo for human review.

**Manual mode:** Write the files to a local output directory. The user decides how to apply them (manually, via CI, etc.).

## Config-Driven Mode

When a product configs repository is added as a working directory, the skill can read product configuration automatically instead of requiring all parameters manually.

### How It Works

1. Claude reads the configs repo's CLAUDE.md to discover product-specific context
2. The CLAUDE.md in that repo provides all necessary details: directory structure, config file format, release notes locations, output conventions, and any product-specific instructions
3. Follow the conventions documented there for storing generated files and creating merge requests

### What to Expect From the Config Repo

The config repo's CLAUDE.md should document:
- Where product config files are and what fields are relevant for releases
- Where release notes templates are stored and how to select the right one
- Where to write generated release YAMLs and summaries
- Any product-specific conventions or naming patterns
- Konflux UI URLs for constructing monitoring links

The skill does not assume any particular config file structure -- it relies entirely on the config repo's CLAUDE.md for guidance.

## Release Notes Templates

### Template Format

```yaml
synopsis: "Product Name {version} ({accelerator})"
description: "Product Name"
topic: "Product Name {version} ({accelerator}) is now available."
references:
  - https://example.com/product
solution: ""
```

### Template Variables

- `{version}` - provided via `--version` argument
- `{accelerator}` - provided via `--accelerator` argument

The script replaces all placeholders recursively through all string values.

### Template Selection

- **GA components** - use `ga.yaml` template + GA production release plan
- **Tech preview components** - use `tech-preview.yaml` template + tech preview production release plan
- **Special variants** - if a variant-specific template exists (e.g., `special-variant.yaml`), use it instead of the default GA/TP template

### Release Types

- **RHEA** (default) - Enhancement Advisory, standard feature releases
- **RHSA** - Security Advisory, requires `--cves-file` parameter
  - CVE file format: one CVE per line (CVE-YYYY-NNNNN)
  - Comments starting with # are ignored
  - Empty lines are skipped

## Release Summary

### Structure

```markdown
# Release Summary

## Release Information
- Date: YYYY-MM-DD
- Version: X.Y.Z
- Commit: <sha>
- Source: <repository-url>

## Components

| Component | Status | Release Name | Release Plan |
|-----------|--------|--------------|--------------|
| component-1 | Ready | name-prod-1 | plan-prod |
| component-2 | Ready | name-prod-2 | plan-tp-prod |

## Generated Files
- component-1-prod.yaml
- component-2-prod.yaml
```

### Storage

In config-driven mode, follow the config repo's CLAUDE.md for where to store the summary.

In manual mode, store it alongside the generated YAMLs in the output directory.

## Naming Conventions

### Release Names

Pattern: `<component>-<version-dashed>-prod-<seq>`

Example: `my-component-1-2-0-prod-1`

- `<component>` - full component name
- `<version-dashed>` - version with dots replaced by dashes
- `prod` - environment
- `<seq>` - sequence number (auto-incremented)

### ReleasePlan Names

Common patterns:
- GA production: `<app>-prod`
- Tech preview production: `<app>-tech-preview-prod`
- Stage: `<app>-stage`

## Multi-Component Release

For applications with multiple components:

1. Resolve tag/image to SHA (once)
2. Query all stage releases with that SHA
3. Filter to successful releases only
4. For each successful stage release, make a **separate tool call** (no loops or backgrounding):
   - Extract component name and snapshot
   - Determine variant from component name
   - Check if tech preview (from config or user input)
   - Select appropriate release plan and template
   - Auto-increment release sequence number
   - Generate production release YAML via individual script invocation
5. Create output directory with all YAMLs
6. Generate release summary document
7. Commit and open MR for review (config-driven) or deliver locally (manual)

### Component Filtering

Support optional filtering by variant/accelerator type:

User provides a list of types to include.

1. Query all stage releases by SHA
2. Extract component names from labels
3. Match against variant patterns in component names
4. Generate YAMLs only for matched components

## Error Handling

**Tag not found:**
- Verify tag exists in the source repository
- Check tag name capitalization
- Try using commit SHA directly

**No stage releases found:**
- Verify SHA is correct (full 40 characters)
- Check if stage releases have completed
- Verify namespace is correct

**Stage release failed:**
- Check PipelineRun logs
- Do NOT create production releases for failed components
- Report failure to user
- Continue with successful releases only

**Template file not found:**
- Verify template file path is correct
- Check file exists and is readable
- Ensure template is valid YAML

**Template parsing error:**
- Validate YAML syntax in template
- Check for proper indentation
- Ensure all fields are properly quoted if needed

**CVE file not found:**
- Verify file path is correct
- Check file format (one CVE per line)
- Ensure CVEs are in CVE-YYYY-NNNNN format

**Release name already exists:**
- Auto-increment the sequence number
- Query existing releases to find the next available number

**Config repo not available:**
- Fall back to manual mode
- Ask the user for all required parameters directly

## Dependencies

Do NOT proactively check or install dependencies. Run commands and scripts directly. Only use these install scripts if a command fails due to a missing tool.

**Required:** `kubectl`, `jq`, `python3`, `PyYAML`

**Optional:** `glab` (tag resolution), `skopeo` (image inspection)

**Install scripts (use only if needed):**
```bash
tools/jq/install.sh              # jq
tools/kubectl/install.sh         # kubectl
tools/skopeo/install.sh          # skopeo
tools/glab/install.sh            # glab
# PyYAML is installed via pip (tools/python/konflux-release-requirements.txt)
```

## Best Practices

**Always use full SHAs** - label selectors require full 40-character SHAs. Short SHAs won't match.

**Verify before generating** - all stage releases must succeed and snapshots must be captured before generating production YAMLs.

**Coordinate parameters correctly:**
- GA releases require: GA template + GA ReleasePlan name
- Tech preview releases require: TP template + TP ReleasePlan name
- The script has no awareness of release type - you control this via parameter selection

**Use release notes templates** - store templates in version control, use `{version}` and `{accelerator}` placeholders for dynamic content.

**Generate summaries** - document what was released, include verification steps and links.

**Review before applying** - generated files should always go through human review before being applied to the cluster.
