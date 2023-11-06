# Common functions for the shell scripts in this directory

# Return the Eliot base URL for the given environment
eliot_base_url() {
    case "$1" in
        aws-stage)  echo "https://symbolication.stage.mozaws.net";;
        aws-prod)   echo "https://symbolication.services.mozilla.com";;
        gcp-stage)  echo "https://stage.eliot.nonprod.dataservices.mozgcp.net";;
        gcp-prod)   echo "https://prod.eliot.prod.dataservices.mozgcp.net";;
        *)
            echo >&2 "Unknown environment. Use 'aws-stage', 'aws-prod', 'gcp-stage' or 'gcp-prod'."
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
    echo ">>> Host:    ${HOST}"

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
