# Common functions for the shell scripts in this directory

# Return the Eliot base URL for the given environment
tecken_base_url() {
    case "$1" in
        aws_stage)  echo "https://symbols.stage.mozaws.net";;
        gcp_stage)  echo "https://tecken-stage.symbols.nonprod.webservices.mozgcp.net/";;
        *)
            echo >&2 "Unknown environment. Use 'aws_stage' or 'gcp_stage'."
            echo >&2 "Exiting."
            exit 1
    esac
}

# Run the load test. Expects these variables to be set:
#
# HOST: the Eliot base URL
# RUNNAME_SUFFIX: suffix appended to the log directory name
# USERS: number of concurrent users
# RUNTIME: duration of the load test
run_loadtest() {
    echo ">>> Environment: ${TARGET_ENV}"
    echo ">>> Host:        ${HOST}"

    mkdir -p logs
    LOCUST_FLAGS="${LOCUST_FLAGS:---headless}"
    DATE="$(date +'%Y%m%d-%H0000')"
    RUNNAME="${DATE}-${RUNNAME_SUFFIX}"

    read -p "Ready to start? " nextvar
    echo "$(date): Locust start ${RUNNAME}...."
    locust -f testfile.py \
        --host="${HOST}" \
        --users="${USERS}" \
        --run-time="${RUNTIME}" \
        --csv="logs/${RUNNAME}" \
        ${LOCUST_FLAGS}
    echo "$(date): Locust end ${RUNNAME}."

    echo "${RUNNAME} users=${USERS} runtime=${RUNTIME}"
    python ../bin/print_locust_stats.py "logs/${RUNNAME}"
}
