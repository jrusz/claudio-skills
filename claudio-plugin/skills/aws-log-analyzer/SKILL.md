---
name: aws-log-analyzer
description: Troubleshoot and analyze logs from AWS CloudWatch Logs. This skill should be used when the user asks to investigate logs, troubleshoot application issues, query log groups, analyze error patterns, or perform log analysis for machines writing to AWS CloudWatch. Uses the AWS CLI for CloudWatch Logs operations.
allowed-tools: Bash(aws logs:*),Bash(*/aws-log-analyzer/scripts/*.sh:*),Bash(*/tools/*/install.sh:*)
---

# AWS Log Analyzer

## Overview

Troubleshoot and analyze logs from AWS CloudWatch Logs - AWS's centralized logging service for applications and infrastructure.

**Prerequisites:**
- `aws` CLI is installed and configured
- User is already authenticated (via IAM credentials, SSO, or instance profile)
- Appropriate IAM permissions for CloudWatch Logs read operations

**Installation:**
Use the centralized tool installation scripts to install dependencies:

```bash
# AWS CLI (required)
../../../tools/aws-cli/install.sh          # Check and install AWS CLI
../../../tools/aws-cli/install.sh --check  # Check only, don't install

# jq (optional, recommended)
../../../tools/jq/install.sh               # Check and install jq
../../../tools/jq/install.sh --check       # Check only, don't install
```

The tool scripts are idempotent - safe to run multiple times. They will only install if the tool is not present or outdated.

**Philosophy:**
Start broad, then narrow down. List log groups → identify relevant streams → filter/query specific events. Use CloudWatch Logs Insights for complex analysis.

## Core Concepts

- **Log Group**: Container for log streams (typically one per application/service)
- **Log Stream**: Sequence of log events from a single source (e.g., instance, container)
- **Log Event**: Individual log entry with timestamp and message
- **CloudWatch Logs Insights**: SQL-like query language for advanced log analysis

## Basic Commands

### List Log Groups

```bash
# List all log groups
aws logs describe-log-groups

# List with filtering
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/

# Get specific details with jq
aws logs describe-log-groups --query 'logGroups[*].[logGroupName,storedBytes]' --output table
```

### List Log Streams

```bash
# List log streams in a group
aws logs describe-log-streams --log-group-name <log-group-name>

# List recent streams (sorted by last event time)
aws logs describe-log-streams \
  --log-group-name <log-group-name> \
  --order-by LastEventTime \
  --descending \
  --max-items 10

# Find streams by prefix
aws logs describe-log-streams \
  --log-group-name <log-group-name> \
  --log-stream-name-prefix <prefix>
```

### Get Log Events

```bash
# Get events from a specific stream
aws logs get-log-events \
  --log-group-name <log-group-name> \
  --log-stream-name <log-stream-name>

# Get recent events (last N)
aws logs get-log-events \
  --log-group-name <log-group-name> \
  --log-stream-name <log-stream-name> \
  --limit 100

# Get events in time range (epoch milliseconds)
aws logs get-log-events \
  --log-group-name <log-group-name> \
  --log-stream-name <log-stream-name> \
  --start-time <start-epoch-ms> \
  --end-time <end-epoch-ms>
```

### Filter Log Events

**Most useful for troubleshooting** - searches across multiple streams:

```bash
# Filter events across all streams in a log group
aws logs filter-log-events \
  --log-group-name <log-group-name> \
  --filter-pattern "ERROR"

# Filter with time range
aws logs filter-log-events \
  --log-group-name <log-group-name> \
  --filter-pattern "ERROR" \
  --start-time <start-epoch-ms> \
  --end-time <end-epoch-ms>

# Filter specific log streams
aws logs filter-log-events \
  --log-group-name <log-group-name> \
  --log-stream-names <stream1> <stream2> \
  --filter-pattern "ERROR"

# Output with jq for better formatting
aws logs filter-log-events \
  --log-group-name <log-group-name> \
  --filter-pattern "ERROR" \
  | jq -r '.events[] | "\(.timestamp | tonumber / 1000 | strftime("%Y-%m-%d %H:%M:%S")) [\(.logStreamName)] \(.message)"'
```

### Tail Logs in Real-Time

```bash
# Tail logs (follow mode)
aws logs tail <log-group-name> --follow

# Tail with filter
aws logs tail <log-group-name> --follow --filter-pattern "ERROR"

# Tail since specific time
aws logs tail <log-group-name> --since 1h --follow

# Tail specific streams
aws logs tail <log-group-name> --follow --log-stream-names <stream-name>
```

**Time formats for --since:**
- `1h` - last hour
- `30m` - last 30 minutes
- `2d` - last 2 days
- `5s` - last 5 seconds

## CloudWatch Logs Insights

For complex queries and analysis, use CloudWatch Logs Insights:

```bash
# Run an Insights query
aws logs start-query \
  --log-group-name <log-group-name> \
  --start-time <start-epoch-seconds> \
  --end-time <end-epoch-seconds> \
  --query-string '<insights-query>'

# Get query results (after starting query)
aws logs get-query-results --query-id <query-id>
```

**Common Insights Query Patterns:**

```sql
# Count errors by type
fields @timestamp, @message
| filter @message like /ERROR/
| stats count() by @message
| sort count desc

# Find slowest requests
fields @timestamp, duration, request_id
| filter duration > 1000
| sort duration desc
| limit 20

# Error rate over time
fields @timestamp, @message
| filter @message like /ERROR/
| stats count() as error_count by bin(5m)

# Parse JSON logs and aggregate
fields @timestamp, @message
| parse @message '{"level":"*","msg":"*","user":"*"}' as level, msg, user
| filter level = "ERROR"
| stats count() by user

# Find exceptions with stack traces
fields @timestamp, @message
| filter @message like /Exception/
| display @timestamp, @message
| limit 50
```

## Filter Pattern Syntax

CloudWatch Logs supports pattern matching for filtering:

**Basic patterns:**
```bash
# Exact match
--filter-pattern "ERROR"

# Multiple terms (AND)
--filter-pattern "ERROR timeout"

# Multiple terms (OR)
--filter-pattern "?ERROR ?WARN ?FATAL"

# Exclusion
--filter-pattern "[email protected]"

# Field extraction (JSON logs)
--filter-pattern '{ $.level = "ERROR" }'

# Numeric filtering
--filter-pattern '{ $.status_code >= 500 }'

# Multiple conditions
--filter-pattern '{ $.level = "ERROR" && $.user_id = "12345" }'
```

**Structured log patterns:**
```bash
# Apache/Nginx access logs
--filter-pattern '[ip, user, username, timestamp, request, status_code >= 400, bytes]'

# Custom delimited logs
--filter-pattern '[time, request_id, level = ERROR, message]'
```

## Troubleshooting Workflows

### Workflow 1: Investigate Recent Errors

**User:** "Check for errors in the past hour for my application"

```bash
# 1. List log groups to find the right one
aws logs describe-log-groups --log-group-name-prefix /aws/application

# 2. Calculate time range (epoch milliseconds)
START_TIME=$(date -d '1 hour ago' +%s)000
END_TIME=$(date +%s)000

# 3. Filter for errors
aws logs filter-log-events \
  --log-group-name /aws/application/myapp \
  --filter-pattern "ERROR" \
  --start-time $START_TIME \
  --end-time $END_TIME \
  | jq -r '.events[] | "\(.timestamp | tonumber / 1000 | strftime("%Y-%m-%d %H:%M:%S")) \(.message)"'

# 4. If too many results, use Insights for aggregation
QUERY_ID=$(aws logs start-query \
  --log-group-name /aws/application/myapp \
  --start-time $START_TIME \
  --end-time $END_TIME \
  --query-string 'fields @timestamp, @message | filter @message like /ERROR/ | stats count() by @message | sort count desc' \
  --query 'queryId' --output text)

# Wait a few seconds for query to complete
sleep 5

# Get results
aws logs get-query-results --query-id $QUERY_ID
```

### Workflow 2: Trace Request Through Multiple Services

**User:** "Trace request ID abc-123 through all services"

```bash
# 1. Find all log groups for the application
LOG_GROUPS=$(aws logs describe-log-groups \
  --log-group-name-prefix /aws/myapp \
  --query 'logGroups[*].logGroupName' \
  --output text)

# 2. Search each log group for the request ID
for LOG_GROUP in $LOG_GROUPS; do
  echo "=== Searching $LOG_GROUP ==="
  aws logs filter-log-events \
    --log-group-name "$LOG_GROUP" \
    --filter-pattern "abc-123" \
    | jq -r '.events[] | "\(.timestamp | tonumber / 1000 | strftime("%Y-%m-%d %H:%M:%S")) [\(.logStreamName)] \(.message)"'
done
```

### Workflow 3: Analyze Performance Issues

**User:** "Find slow database queries in the last 24 hours"

```bash
# Use Insights for advanced analysis
START_TIME=$(date -d '24 hours ago' +%s)
END_TIME=$(date +%s)

QUERY_ID=$(aws logs start-query \
  --log-group-name /aws/rds/instance/mydb/slowquery \
  --start-time $START_TIME \
  --end-time $END_TIME \
  --query-string '
    fields @timestamp, query_time, lock_time, rows_examined, @message
    | parse @message /Query_time: (?<qt>[0-9.]+)\s+Lock_time: (?<lt>[0-9.]+).*\n(?<query>.*)/
    | filter qt > 1.0
    | sort qt desc
    | limit 20
  ' \
  --query 'queryId' --output text)

sleep 5
aws logs get-query-results --query-id $QUERY_ID
```

### Workflow 4: Monitor for Specific Error Pattern

**User:** "Watch for OutOfMemory errors in real-time"

```bash
# Tail with filter pattern
aws logs tail /aws/application/myapp \
  --follow \
  --filter-pattern "OutOfMemoryError" \
  --format short
```

## Helper Scripts

This skill includes helper scripts in `scripts/` directory.

### Tool Installation

Installation scripts are available in the `claudio-plugin/tools/` directory for all required dependencies:

**AWS CLI (required):**
```bash
# Install or update AWS CLI
../../../tools/aws-cli/install.sh

# Check installation status
../../../tools/aws-cli/install.sh --check
```

**jq (optional, recommended):**
```bash
# Install or update jq
../../../tools/jq/install.sh

# Check installation status
../../../tools/jq/install.sh --check
```

**Features:**
- Automatically detects architecture
- Downloads and installs correct binary for your platform
- Version tracking for Renovate (see script headers)
- Supports Linux (x86_64, aarch64)
- No root access required (installs to `~/.local/bin` if `/usr/local/bin` is not writable)

### Log Time Range Calculator

```bash
# Calculate epoch milliseconds for common time ranges
scripts/time_range.sh "1 hour ago"
scripts/time_range.sh "2024-01-15 10:00:00" "2024-01-15 11:00:00"
```

### Multi-Group Search

```bash
# Search across multiple log groups for a pattern
scripts/multi_group_search.sh "ERROR" "/aws/lambda/*"
```

## Time Handling

**Important:** Different AWS Logs commands use different time formats:

- `filter-log-events`: Epoch milliseconds (`1234567890000`)
- `start-query`: Epoch seconds (`1234567890`)
- `tail --since`: Human-readable (`1h`, `30m`, `2d`)

**Convert to epoch milliseconds:**
```bash
# Current time
date +%s000

# Specific time
date -d "2024-01-15 10:00:00" +%s000

# Relative time (1 hour ago)
date -d "1 hour ago" +%s000
```

**Convert from epoch milliseconds to human-readable:**
```bash
echo "1705315200000" | awk '{print strftime("%Y-%m-%d %H:%M:%S", $1/1000)}'
```

## Output Formatting

### Pretty-print log events with jq

```bash
# Format with timestamp, stream, and message
aws logs filter-log-events \
  --log-group-name <log-group> \
  --filter-pattern "ERROR" \
  | jq -r '.events[] | "\(.timestamp | tonumber / 1000 | strftime("%Y-%m-%d %H:%M:%S")) [\(.logStreamName)] \(.message)"'

# Extract JSON log fields
aws logs filter-log-events \
  --log-group-name <log-group> \
  --filter-pattern "ERROR" \
  | jq -r '.events[].message | fromjson | "\(.timestamp) [\(.level)] \(.message)"'

# Count events by log stream
aws logs filter-log-events \
  --log-group-name <log-group> \
  --filter-pattern "ERROR" \
  | jq -r '.events | group_by(.logStreamName) | map({stream: .[0].logStreamName, count: length}) | .[]'
```

## Best Practices

**Start broad, then narrow:**
1. List log groups to find the right one
2. Check recent log streams to understand activity
3. Use `filter-log-events` for simple searches across streams
4. Use Insights for complex aggregations and analysis

**Time range considerations:**
- Narrow time ranges reduce query cost and improve performance
- Start with recent time ranges (last hour, last 6 hours)
- Expand if needed

**Filter patterns vs Insights:**
- Use filter patterns for simple text matching
- Use Insights for aggregations, parsing, and complex analysis
- Insights has a cost per GB scanned

**Pagination:**
- `filter-log-events` returns max 10,000 events
- Use `--next-token` for pagination
- Or use time-based chunking for large searches

**Performance tips:**
- Specify log streams when known (faster than searching all streams)
- Use specific filter patterns (reduces data scanned)
- Limit results with `--max-items` or `--limit`

**Common gotchas:**
- Timestamps are in milliseconds for filter-log-events, seconds for start-query
- Log stream names must match exactly (case-sensitive)
- Filter patterns are case-sensitive by default
- Insights queries have a max execution time of 15 minutes

## Integration with Other Skills

**kubernetes skill:**
- Get pod names from k8s → search CloudWatch log streams for those pods
- Match k8s events with application logs

**gitlab skill:**
- Get commit SHA → search logs for deployment events with that SHA
- Correlate CI/CD pipeline failures with application errors

## Common Log Group Patterns

**AWS Services:**
```
/aws/lambda/<function-name>           # Lambda functions
/aws/rds/instance/<instance-id>/*     # RDS instances
/aws/ecs/containerinsights/<cluster>  # ECS container insights
/aws/eks/<cluster>/cluster            # EKS control plane
/aws/apigateway/<api-id>/<stage>      # API Gateway
```

**Application Logs:**
```
/aws/application/<app-name>           # Custom application
/var/log/messages                     # System logs
/aws/containerinsights/<cluster>/*    # Container logs
```

## Error Handling

**Log group not found:**
- Verify log group name (case-sensitive)
- Check AWS region (use `--region` flag)
- Verify IAM permissions

**No events found:**
- Verify time range (check time zone)
- Check filter pattern syntax
- Ensure log streams exist in that time range

**Query timeout:**
- Reduce time range
- Simplify Insights query
- Add more specific filters

**Access denied:**
- Verify IAM permissions: `logs:FilterLogEvents`, `logs:DescribeLogGroups`, etc.
- Check resource-based policies on log groups

## Dependencies

**Required:**
- `aws` - AWS CLI v2 (recommended) or v1
  - Use `claudio-plugin/tools/aws-cli/install.sh` to automatically install if missing
  - Version is tracked in the script for Renovate updates

**Optional:**
- `jq` - JSON processor for parsing and formatting outputs
  - Use `claudio-plugin/tools/jq/install.sh` to automatically install if missing
  - Version is tracked in the script for Renovate updates
- `date` - GNU date for time calculations (typically pre-installed on Linux)

**Installation:**
Individual installation scripts are available in the `claudio-plugin/tools/` directory:
- `tools/aws-cli/install.sh` - AWS CLI installation
- `tools/jq/install.sh` - jq installation

Each script:
- Detects your platform (Linux/macOS, x86_64/ARM64)
- Downloads and installs the correct binary for your platform
- Tracks version for automatic updates via Renovate
- No root access required (installs to `~/.local/bin` if `/usr/local/bin` is not writable)
