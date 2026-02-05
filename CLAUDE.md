# Claudio Skills Plugin

## Overview

This repository contains **Claudio Skills Plugin** - a Claude Code plugin that extends Claude with specialized skills for DevOps and cloud-native development workflows. The plugin provides four powerful skills designed to streamline interactions with GitLab, Kubernetes, Konflux, and AWS CloudWatch Logs.

## What is this for?

This plugin enables Claude Code to:

- **Interact with GitLab repositories** using the official `glab` CLI
- **Manage Kubernetes clusters** using `kubectl` operations
- **Orchestrate Konflux releases** for production deployments
- **Troubleshoot and analyze AWS CloudWatch Logs** for application debugging and monitoring

These skills allow you to leverage Claude as an intelligent assistant for complex DevOps tasks, from querying merge requests to deploying production releases and troubleshooting application issues across multiple components.

## Plugin Structure

```
claudio-plugin/
├── .claude-plugin/
│   └── plugin.json              # Plugin metadata
├── tools/
│   ├── common.sh                # Shared library for tool installers
│   ├── TOOLS.md                 # Tool installation guide
│   ├── aws-cli/
│   │   └── install.sh           # AWS CLI installer
│   └── jq/
│       └── install.sh           # jq installer
└── skills/
    ├── gitlab/
    │   └── SKILL.md             # GitLab operations skill
    ├── kubernetes/
    │   └── SKILL.md             # Kubernetes management skill
    ├── konflux/
    │   ├── SKILL.md             # Konflux release workflow skill
    │   └── scripts/
    │       └── generate_release_yaml.py  # Release YAML generator
    └── aws-log-analyzer/
        ├── SKILL.md             # AWS CloudWatch Logs troubleshooting skill
        └── scripts/
            ├── time_range.sh    # Time range calculator
            └── multi_group_search.sh  # Multi-group search tool
```

## Tools Management

The `claudio-plugin/tools/` directory contains centralized installation scripts for CLI tools used by skills. This system provides a consistent, maintainable way to manage tool dependencies across all skills.

### Philosophy

**Design Principles:**
- **Simplicity:** Scripts do one thing well - install the tool if not present
- **Reusability:** Common functions are shared via `common.sh` library
- **Linux-only:** Focus on Linux x86_64 and ARM64 (aarch64) architectures
- **Minimal options:** Only `--check` flag for verification
- **Idempotent:** Safe to run multiple times

### Directory Structure

```
claudio-plugin/tools/
├── common.sh              # Shared library with common functions
├── TOOLS.md              # Comprehensive guide for adding new tools
├── <tool-name>/
│   └── install.sh        # Installation script for the tool
└── ...
```

### Common Library (`common.sh`)

The `common.sh` library provides shared functions used across all tool installation scripts:

**Available Functions:**
- `log()` - Simple logging to stdout
- `detect_arch()` - Detect architecture (x86_64 or aarch64)
- `verify_linux()` - Verify running on Linux
- `command_exists()` - Check if command exists in PATH
- `version_gte()` - Semantic version comparison
- `is_in_path()` - Check if directory is in PATH
- `warn_if_not_in_path()` - Warn if install directory not in PATH

**Usage in scripts:**
```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../common.sh"
```

### Currently Available Tools

**AWS CLI** (`tools/aws-cli/install.sh`)
- Installs AWS CLI v2
- Used by: aws-log-analyzer skill
- Supports: Linux x86_64, ARM64

**jq** (`tools/jq/install.sh`)
- Installs jq JSON processor
- Used by: Multiple skills for JSON parsing
- Supports: Linux x86_64, ARM64

### Adding New Tools

**When a skill requires a new CLI tool, follow this process:**

1. **Check if the tool already exists** in `claudio-plugin/tools/`

2. **Read the comprehensive guide:** `claudio-plugin/tools/TOOLS.md`
   - Contains complete template
   - Installation patterns (binary, archive, package manager)
   - Common pitfalls and best practices
   - Testing checklist

3. **Create the tool directory:**
   ```bash
   mkdir -p claudio-plugin/tools/<tool-name>
   ```

4. **Use the template** from `TOOLS.md` and customize:
   - Replace placeholders with tool-specific details
   - Add Renovate version tracking
   - Implement version detection
   - Add download URLs for x86_64 and ARM64
   - Choose appropriate installation pattern

5. **Key Guidelines:**
   - ✓ **Use `common.sh` functions** - Always check for existing functions first
   - ✓ **Linux x86_64 and ARM64 only** - No macOS, Windows, or other architectures
   - ✓ **Minimal options** - Only support `--check` flag
   - ✓ **Version tracking** - Use Renovate comments for automatic updates
   - ✓ **Idempotent** - Safe to run multiple times
   - ✗ **Don't add** `--help`, `--version`, or `--force` flags
   - ✗ **Don't duplicate** functions from `common.sh`

6. **Test the script:**
   ```bash
   # Check syntax
   bash -n tools/<tool>/install.sh

   # Test installation
   tools/<tool>/install.sh

   # Test idempotency
   tools/<tool>/install.sh
   ```

7. **Update skill documentation** to reference the new tool

8. **Update skill's `check_deps.sh`** if the skill uses one

### Script Template Summary

Each tool installer follows this structure:

```bash
#!/usr/bin/env bash
# Header with usage

set -euo pipefail

# Load common.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../common.sh"

# Version tracking for Renovate
# renovate: datasource=github-releases depName=org/repo
TOOL_VERSION="x.y.z"

# Configuration (install directory detection)

# get_tool_version() - Extract version from tool
# check_tool() - Verify installation and version
# install_tool() - Download and install for detected architecture

# main() - Parse --check flag, install if needed
```

### Example: Using Tool Installers

**From a skill's dependency checker:**
```bash
# skills/my-skill/scripts/check_deps.sh

AWS_CLI_INSTALL_SCRIPT="$TOOLS_DIR/aws-cli/install.sh"

# Check if installed
"$AWS_CLI_INSTALL_SCRIPT" --check

# Install if needed
"$AWS_CLI_INSTALL_SCRIPT"
```

**Direct usage:**
```bash
# Check if AWS CLI is installed
claudio-plugin/tools/aws-cli/install.sh --check

# Install AWS CLI if needed
claudio-plugin/tools/aws-cli/install.sh
```

### Version Management with Renovate

All tool installers use Renovate for automatic version updates:

```bash
# renovate: datasource=github-releases depName=aws/aws-cli
AWS_CLI_VERSION="2.15.17"
```

When a new version is released, Renovate automatically creates a PR to update the version.

### For Complete Documentation

**See `claudio-plugin/tools/TOOLS.md` for:**
- Complete script template with all sections
- Detailed function documentation
- 3 installation patterns (binary, archive, package manager)
- Common pitfalls with examples
- Step-by-step walkthrough for adding a new tool
- Testing checklist
- Maintenance guidelines

**This is the authoritative guide for all tool installation scripts.**

## Skills Included

### 1. GitLab Skill

**Purpose:** Interact with GitLab repositories using the `glab` CLI tool.

**Use cases:**
- List and view merge requests
- Check pipeline and job status
- Resolve git tags to commit SHAs
- Manage issues, releases, and repository metadata
- View merge request diffs and CI/CD pipelines

**Key features:**
- Prefers built-in `glab` commands over API calls
- Falls back to `glab api --method GET` for operations not covered by built-in commands
- Supports GitLab.com, Self-Managed, and Dedicated instances
- Safe read-only operations by default

### 2. Kubernetes Skill

**Purpose:** Interact with Kubernetes clusters using `kubectl` commands.

**Use cases:**
- Get and describe Kubernetes resources (pods, deployments, services, etc.)
- Filter resources using label selectors
- Query resources across namespaces
- Extract specific fields using jq

**Key features:**
- Follows "default first, then JSON drill-down" pattern to avoid context pollution
- Efficient querying with namespace and label filtering
- JSON output for programmatic processing
- Works with pre-configured kubectl contexts

### 3. Konflux Skill

**Purpose:** Work with Konflux - a build and release platform based on OpenShift and Tekton.

**Use cases:**
- Create production releases from successful stage releases
- Query Konflux Release, Snapshot, and ReleasePlan resources
- Generate release YAMLs with release notes
- Orchestrate multi-component releases
- Follow stage-to-production deployment workflows

**Key features:**
- Automates stage → production release pattern
- Extracts metadata from stage releases
- Applies release notes templates with version/variant substitution
- Includes Python script for deterministic YAML generation
- Integrates with GitLab skill for tag resolution and Kubernetes skill for resource querying

### 4. AWS Log Analyzer Skill

**Purpose:** Troubleshoot and analyze logs from AWS CloudWatch Logs for debugging and monitoring.

**Use cases:**
- Investigate errors and exceptions across log groups
- Trace requests through multiple services
- Analyze performance issues and slow queries
- Monitor for specific error patterns in real-time
- Perform complex log aggregations and analysis

**Key features:**
- Supports CloudWatch Logs filter patterns and Insights queries
- Real-time log tailing with filtering
- Multi-log-group search capabilities
- Efficient time range handling (epoch conversion)
- Pretty-printing and JSON parsing with jq
- Helper scripts for common operations

## Prerequisites

Each skill has its own dependencies:

**GitLab Skill:**
- `glab` - GitLab CLI tool
- User already authenticated
- Optional: `jq` for JSON parsing

**Kubernetes Skill:**
- `kubectl` - Kubernetes CLI
- Configured kubectl context
- Optional: `jq` for JSON parsing

**Konflux Skill:**
- `kubectl` (via kubernetes skill)
- `glab` (via gitlab skill)
- `python3` for YAML generation script
- `jq` for JSON parsing

**AWS Log Analyzer Skill:**
- `aws` CLI - AWS CLI v2 recommended
- User already authenticated (IAM credentials, SSO, or instance profile)
- Optional: `jq` for JSON parsing and output formatting

## Installation

This plugin is configured in the marketplace at `.claude-plugin/marketplace.json` and can be loaded by Claude Code from the local `claudio-plugin` directory.

## Usage Philosophy

The skills follow these principles:

1. **Tool preference:** Use native CLI commands over API calls when possible
2. **Efficient querying:** Start with table output, drill down to specific resources
3. **Read-only by default:** Prefer GET operations for safety
4. **Integration:** Skills work together (e.g., Konflux uses GitLab and Kubernetes skills)
5. **Context efficiency:** Avoid dumping large JSON outputs unless necessary

## Example Workflows

### Production Release Workflow (Konflux + GitLab + Kubernetes)

When a user asks to create a production release:

1. **Resolve tag to commit SHA** (GitLab skill)
   ```bash
   glab api --method GET projects/owner%2Frepo/repository/commits/v1.2.3 | jq -r '.id'
   ```

2. **Find stage releases by SHA** (Kubernetes skill)
   ```bash
   kubectl get releases -n namespace -l "pac.test.appstudio.openshift.io/sha=<full-sha>"
   ```

3. **Filter to successful releases** (Kubernetes skill)
   - Check `.status.conditions[type=Released].status = "True"`

4. **Generate production YAMLs** (Konflux skill)
   ```bash
   scripts/generate_release_yaml.py \
     --stage-release <stage-release-name> \
     --version 1.2.3 \
     --namespace <namespace> \
     --output out/component-prod.yaml
   ```

5. **Deploy releases** (Kubernetes skill)
   ```bash
   kubectl apply -f out/
   ```

### Log Troubleshooting Workflow (AWS Log Analyzer + Kubernetes)

When a user asks to investigate application errors:

1. **Identify the log group** (AWS Log Analyzer skill)
   ```bash
   aws logs describe-log-groups --log-group-name-prefix /aws/application/
   ```

2. **Search for recent errors** (AWS Log Analyzer skill)
   ```bash
   scripts/time_range.sh "1 hour ago"
   aws logs filter-log-events \
     --log-group-name /aws/application/myapp \
     --filter-pattern "ERROR" \
     --start-time $START_TIME \
     --end-time $END_TIME
   ```

3. **Correlate with pod events** (Kubernetes skill)
   ```bash
   kubectl get events --sort-by='.lastTimestamp'
   ```

4. **Trace request across services** (AWS Log Analyzer skill)
   ```bash
   scripts/multi_group_search.sh "request-id-12345" "/aws/application/"
   ```

5. **Analyze error patterns** (AWS Log Analyzer skill - using Insights)
   ```bash
   aws logs start-query \
     --log-group-name /aws/application/myapp \
     --query-string 'fields @timestamp, @message | filter @message like /ERROR/ | stats count() by @message'
   ```

## License

Apache License 2.0 - See LICENSE file for details.

## Author

Claudio (v0.1.0)
