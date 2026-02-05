#!/usr/bin/env bash
#
# Search across multiple CloudWatch Log Groups
#
# Usage:
#   multi_group_search.sh "ERROR" "/aws/lambda/*"
#   multi_group_search.sh --pattern "OutOfMemory" --prefix "/aws/application"

set -euo pipefail

show_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] <search-pattern> <log-group-pattern>

Search for a pattern across multiple CloudWatch Log Groups.

ARGUMENTS:
    search-pattern          Pattern to search for (CloudWatch filter pattern)
    log-group-pattern       Log group name or prefix pattern

OPTIONS:
    -h, --help              Show this help message
    -s, --start-time TIME   Start time (e.g., "1 hour ago")
    -e, --end-time TIME     End time (default: now)
    -r, --region REGION     AWS region (default: from AWS config)
    -l, --limit NUM         Max events per log group (default: 100)
    --json                  Output raw JSON instead of formatted text
    --summary               Show only summary (count per log group)

EXAMPLES:
    # Search for errors in all Lambda functions
    $(basename "$0") "ERROR" "/aws/lambda/"

    # Search in last hour with time range
    $(basename "$0") -s "1 hour ago" "timeout" "/aws/application/"

    # Get summary counts only
    $(basename "$0") --summary "ERROR" "/aws/ecs/"

    # Search specific pattern in RDS logs
    $(basename "$0") "slow query" "/aws/rds/instance/"

EOF
}

# Default options
START_TIME=""
END_TIME=""
REGION=""
LIMIT=100
OUTPUT_FORMAT="formatted"
SUMMARY_ONLY=false

# Parse options
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        -s|--start-time)
            START_TIME="$2"
            shift 2
            ;;
        -e|--end-time)
            END_TIME="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -l|--limit)
            LIMIT="$2"
            shift 2
            ;;
        --json)
            OUTPUT_FORMAT="json"
            shift
            ;;
        --summary)
            SUMMARY_ONLY=true
            shift
            ;;
        *)
            break
            ;;
    esac
done

if [[ $# -lt 2 ]]; then
    echo "Error: Missing required arguments" >&2
    show_usage
    exit 1
fi

SEARCH_PATTERN="$1"
LOG_GROUP_PATTERN="$2"

# Build AWS CLI base command
AWS_CMD="aws logs"
if [[ -n "$REGION" ]]; then
    AWS_CMD="$AWS_CMD --region $REGION"
fi

# Calculate time range if provided
TIME_ARGS=""
if [[ -n "$START_TIME" ]]; then
    START_EPOCH=$(date -d "$START_TIME" +%s)000
    TIME_ARGS="--start-time $START_EPOCH"
fi
if [[ -n "$END_TIME" ]]; then
    END_EPOCH=$(date -d "$END_TIME" +%s)000
    TIME_ARGS="$TIME_ARGS --end-time $END_EPOCH"
fi

# Find matching log groups
echo "Finding log groups matching: $LOG_GROUP_PATTERN" >&2

LOG_GROUPS=$($AWS_CMD describe-log-groups \
    --log-group-name-prefix "$LOG_GROUP_PATTERN" \
    --query 'logGroups[*].logGroupName' \
    --output text)

if [[ -z "$LOG_GROUPS" ]]; then
    echo "Error: No log groups found matching: $LOG_GROUP_PATTERN" >&2
    exit 1
fi

LOG_GROUP_COUNT=$(echo "$LOG_GROUPS" | wc -w)
echo "Found $LOG_GROUP_COUNT log group(s)" >&2
echo "" >&2

# Search each log group
TOTAL_EVENTS=0

for LOG_GROUP in $LOG_GROUPS; do
    echo "=== Searching: $LOG_GROUP ===" >&2

    # Build filter command
    FILTER_CMD="$AWS_CMD filter-log-events \
        --log-group-name \"$LOG_GROUP\" \
        --filter-pattern \"$SEARCH_PATTERN\" \
        --limit $LIMIT \
        $TIME_ARGS"

    # Execute search
    RESULT=$(eval "$FILTER_CMD" 2>/dev/null || echo '{"events":[]}')

    EVENT_COUNT=$(echo "$RESULT" | jq -r '.events | length')
    TOTAL_EVENTS=$((TOTAL_EVENTS + EVENT_COUNT))

    if [[ "$SUMMARY_ONLY" == "true" ]]; then
        echo "$LOG_GROUP: $EVENT_COUNT events" >&2
    elif [[ "$OUTPUT_FORMAT" == "json" ]]; then
        echo "$RESULT"
    else
        if [[ "$EVENT_COUNT" -gt 0 ]]; then
            echo "$RESULT" | jq -r '.events[] | "\(.timestamp | tonumber / 1000 | strftime("%Y-%m-%d %H:%M:%S")) [\(.logStreamName)] \(.message)"'
        else
            echo "  No events found" >&2
        fi
    fi

    echo "" >&2
done

echo "=== Summary ===" >&2
echo "Total log groups searched: $LOG_GROUP_COUNT" >&2
echo "Total events found: $TOTAL_EVENTS" >&2
