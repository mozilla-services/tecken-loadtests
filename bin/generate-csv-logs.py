#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import csv
from datetime import datetime
from glob import glob
from collections import defaultdict
import os
import boto
import boto.s3.connection


# From
# https://blog.kowalczyk.info/article/a1e/Parsing-s3-log-files-in-python.html
import re

s3_line_logpats = (
    r"(\S+) (\S+) \[(.*?)\] (\S+) (\S+) "
    r'(\S+) (\S+) (\S+) "([^"]+)" '
    r"(\S+) (\S+) (\S+) (\S+) (\S+) (\S+) "
    r'"([^"]+)" "([^"]+)"'
)

s3_line_logpat = re.compile(s3_line_logpats)

(
    S3_LOG_BUCKET_OWNER,
    S3_LOG_BUCKET,
    S3_LOG_DATETIME,
    S3_LOG_IP,
    S3_LOG_REQUESTOR_ID,
    S3_LOG_REQUEST_ID,
    S3_LOG_OPERATION,
    S3_LOG_KEY,
    S3_LOG_HTTP_METHOD_URI_PROTO,
    S3_LOG_HTTP_STATUS,
    S3_LOG_S3_ERROR,
    S3_LOG_BYTES_SENT,
    S3_LOG_OBJECT_SIZE,
    S3_LOG_TOTAL_TIME,
    S3_LOG_TURN_AROUND_TIME,
    S3_LOG_REFERER,
    S3_LOG_USER_AGENT,
) = range(17)

s3_names = (
    "bucket_owner",
    "bucket",
    "datetime",
    "ip",
    "requestor_id",
    "request_id",
    "operation",
    "key",
    "http_method_uri_proto",
    "http_status",
    "s3_error",
    "bytes_sent",
    "object_size",
    "total_time",
    "turn_around_time",
    "referer",
    "user_agent",
)


def parse_s3_log_line(line):
    match = s3_line_logpat.match(line)
    result = [match.group(1 + n) for n in range(17)]
    return result


def dump_parsed_s3_line(parsed):
    log = {}
    for name, val in zip(s3_names, parsed):
        log[name] = val
        # print("%s: %s" % (name, val))
    return log


def summorize():
    with open("symbol-queries.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "DATE",
                "URI",
                "STATUS CODE",
                "PRIVATE",
                "TOTAL_TIME",
            ]
        )
        for dt, uri, status_code, private, total_time in get_all_logs():
            writer.writerow(
                [
                    dt.isoformat(),
                    uri,
                    str(status_code),
                    private and "true" or "false",
                    str(total_time),
                ]
            )


def group():
    hashes = defaultdict(int)
    with open("symbol-queries.csv") as r:
        reader = csv.reader(r)
        next(reader)
        for line in reader:
            dt, uri, status_code, private, total_time = line
            # print(line)
            hash_ = (uri, status_code, private)
            hashes[hash_] += 1

    with open("symbol-queries-groups.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "URI",
                "STATUS CODE",
                "PRIVATE",
                "COUNT",
            ]
        )
        for (uri, status_code, private), count in hashes.items():
            writer.writerow(
                [
                    uri,
                    status_code,
                    private,
                    count,
                ]
            )


def analyze_rates():
    groups = defaultdict(list)
    with open("symbol-queries.csv") as r:
        reader = csv.reader(r)
        next(reader)
        for line in reader:
            dt, uri, status_code, private, total_time = line
            dt = datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S")
            hash_ = (status_code, private)
            groups[hash_].append(dt)

    outs = []
    outs.append(
        (
            "CODE".ljust(10),
            "PRIVATE".ljust(10),
            "COUNT".rjust(10),
            "RATE query/sec",
        )
    )
    for (status_code, private), dts in groups.items():
        max_ = max(dts)
        min_ = min(dts)
        secs = (max_ - min_).total_seconds()
        count = len(dts)
        outs.append(
            (
                status_code.ljust(10),
                private.ljust(10),
                str(count).rjust(10),
                count / secs,
                # "queries per second",
            )
        )
    outs.sort(key=lambda x: x[3], reverse=True)
    for things in outs:
        print(*things)


def median(lst):
    quotient, remainder = divmod(len(lst), 2)
    if remainder:
        return sorted(lst)[quotient]
    return sum(sorted(lst)[quotient - 1 : quotient + 1]) / 2.0


def analyze_total_times():
    groups = defaultdict(list)
    with open("symbol-queries.csv") as r:
        reader = csv.reader(r)
        next(reader)
        for line in reader:
            dt, uri, status_code, private, total_time = line
            # dt = datetime.strptime(dt, '%Y-%m-%dT%H:%M:%S')
            hash_ = (status_code, private)
            groups[hash_].append(int(total_time))

    outs = []
    outs.append(
        (
            "CODE".ljust(10),
            "PRIVATE".ljust(10),
            "COUNT".rjust(10),
            "AVERAGE".rjust(10),
            "MEDIAN".rjust(10),
        )
    )
    for (status_code, private), total_times in groups.items():
        count = len(total_times)
        if count < 10:
            continue
        average = sum(total_times) / count
        med = median(total_times)
        outs.append(
            (
                status_code.ljust(10),
                private.ljust(10),
                str(count).rjust(10),
                str(average).rjust(10),
                str(med).rjust(10),
            )
        )
    outs.sort(key=lambda x: x[3], reverse=True)
    for things in outs:
        print(*things)


def cache_feasibility(*args):
    if args:
        size = int(args[0])
    else:
        size = 300  # default Django cache backend MAX_ENTRIES
    cache = set()
    with open("downloading/symbol-queries.csv") as r:
        reader = csv.reader(r)
        next(reader)
        misses = 0
        hits = 0
        for line in reader:
            dt, uri, status_code, private, total_time = line
            if uri in cache:
                hits += 1
            else:
                misses += 1
            cache.add(uri)
            if len(cache) > size:
                # cull!
                # delete a third
                doomed = [k for (i, k) in enumerate(cache) if i % 3 == 0]
                for k in doomed:
                    cache.remove(k)
        print("Misses:", misses)
        print("Hits:", hits)
        print("Hit ratio", 100 * hits / (hits + misses))


def get_all_logs():
    prefixes = (
        (True, "downloadlogs/private-symbols"),
        (False, "downloadlogs/public-symbols"),
    )
    c = 0
    for private, d in prefixes:
        for fp in glob(os.path.join(d, "*.log")):
            # fp = os.path.join(d)
            with open(fp) as f:
                for line in f:
                    log = dump_parsed_s3_line(parse_s3_log_line(line))
                    dt = datetime.strptime(
                        log["datetime"].split()[0],
                        "%d/%b/%Y:%H:%M:%S",
                    )
                    # print(repr(dt))
                    uri = log["http_method_uri_proto"]
                    if uri.startswith("GET "):
                        uri = uri.split()[1]
                    status_code = int(log.get("http_status"))
                    total_time = int(log["total_time"])
                    # print()
                    yield (
                        dt,
                        uri,
                        status_code,
                        private,
                        total_time,
                    )

                    c += 1

                    # if c> 10000:
                    #     break


def download():
    bucket_location = "us-west-2"
    conn = boto.s3.connect_to_region(
        bucket_location,
        aws_access_key_id=os.environ["AWS_ACCESS_KEY"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        calling_format=boto.s3.connection.OrdinaryCallingFormat(),
    )

    bucket_name = "peterbe-symbols-playground-deleteme-in-2018"
    bucket = conn.lookup(bucket_name)
    print(bucket)
    # prefixes = (('public', 'symbols-public/'), ('private', 'private-symbols/'))
    prefixes = (("public", "symbols-public/"),)
    for _, prefix in prefixes:
        for key in bucket.get_all_keys(prefix=prefix):
            print("KEY", key)
            if key.name.endswith("/"):
                continue
            fp = "downloadlogs/" + key.name + ".log"
            if os.path.isfile(fp):
                continue
            key.get_contents_to_filename(fp)
            print("DOWNLOADED", fp)
            # with open(fp, 'w') as f:
            #     key.get_contents_to_file(f)
            #     print('DOWNLOADED', fp)


if __name__ == "__main__":
    import sys

    arg = sys.argv[1]
    commands = {
        "download": download,
        "summorize": summorize,
        "group": group,
        "analyze_rates": analyze_rates,
        "analyze_total_times": analyze_total_times,
        "cache_feasibility": cache_feasibility,
    }
    commands[arg](*sys.argv[2:])
