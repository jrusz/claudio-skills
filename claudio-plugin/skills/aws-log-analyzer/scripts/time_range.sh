#!/usr/bin/env bash
#
# Calculate epoch milliseconds for AWS CloudWatch Logs time ranges
#
# Usage:
#   time_range.sh "1 hour ago"
#   time_range.sh "2024-01-15 10:00:00" "2024-01-15 11:00:00"
#   time_range.sh --help

set -euo pipefail

show_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] <time-expression> [end-time-expression]

Calculate epoch milliseconds for AWS CloudWatch Logs time ranges.

ARGUMENTS:
    time-expression         Start time (relative or absolute)
    end-time-expression     End time (optional, defaults to now)

TIME EXPRESSION FORMATS:
    Relative:  "1 hour ago", "30 minutes ago", "2 days ago"
    Absolute:  "2024-01-15 10:00:00", "2024-01-15T10:00:00Z"
    Special:   "now"

OUTPUT:
    START_TIME=<epoch-ms>   Start time in epoch milliseconds
    END_TIME=<epoch-ms>     End time in epoch milliseconds

EXAMPLES:
    # Last hour
    $(basename "$0") "1 hour ago"

    # Specific time range
    $(basename "$0") "2024-01-15 10:00:00" "2024-01-15 11:00:00"

    # Last 30 minutes
    $(basename "$0") "30 minutes ago"

    # Use in AWS CLI command
    eval \$($(basename "$0") "1 hour ago")
    aws logs filter-log-events --start-time \$START_TIME --end-time \$END_TIME ...

OPTIONS:
    -h, --help              Show this help message
    --seconds               Output epoch seconds instead of milliseconds
    --human                 Also output human-readable format

EOF
}

# Parse arguments
OUTPUT_FORMAT="ms"
HUMAN_READABLE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        --seconds)
            OUTPUT_FORMAT="s"
            shift
            ;;
        --human)
            HUMAN_READABLE=true
            shift
            ;;
        *)
            break
            ;;
    esac
done

if [[ $# -lt 1 ]]; then
    echo "Error: Missing time expression" >&2
    show_usage
    exit 1
fi

START_EXPR="$1"
END_EXPR="${2:-now}"

# Convert time expression to epoch seconds
convert_to_epoch() {
    local expr="$1"

    if [[ "$expr" == "now" ]]; then
        date +%s
    else
        date -d "$expr" +%s 2>/dev/null || {
            echo "Error: Invalid time expression: $expr" >&2
            exit 1
        }
    fi
}

# Calculate times
START_EPOCH=$(convert_to_epoch "$START_EXPR")
END_EPOCH=$(convert_to_epoch "$END_EXPR")

# Convert to milliseconds if needed
if [[ "$OUTPUT_FORMAT" == "ms" ]]; then
    START_TIME="${START_EPOCH}000"
    END_TIME="${END_EPOCH}000"
else
    START_TIME="$START_EPOCH"
    END_TIME="$END_EPOCH"
fi

# Output
echo "START_TIME=$START_TIME"
echo "END_TIME=$END_TIME"

if [[ "$HUMAN_READABLE" == "true" ]]; then
    echo "# Start: $(date -d "@$START_EPOCH" '+%Y-%m-%d %H:%M:%S %Z')"
    echo "# End:   $(date -d "@$END_EPOCH" '+%Y-%m-%d %H:%M:%S %Z')"
    echo "# Duration: $((END_EPOCH - START_EPOCH)) seconds"
fi
