# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dataclasses import dataclass
from datetime import datetime
import logging
import os
import random
from tempfile import NamedTemporaryFile, TemporaryDirectory
import textwrap
import time
from typing import BinaryIO, Optional
import zipfile

from locust import HttpUser, task
from locust import events
from requests import Session, Response
from requests.adapters import HTTPAdapter, Retry


LOGGER = logging.getLogger(__name__)
TIMEOUT = 120


TARGET_ENV = os.environ["TARGET_ENV"]
HOST = os.environ["HOST"]

ARCHIVE_SIZE = 20_000_000
SYM_SIZE = 1_000_000


class AuthTokenMissing(Exception):
    pass


@dataclass
class Environment:
    """A target environment specification."""

    # The name of the environment
    name: str

    # The base URL of the Tecken instance to test.
    base_url: str

    def env_var_name(self, try_storage: bool) -> str:
        env_var_name = self.name.upper() + "_AUTH_TOKEN"
        if try_storage:
            env_var_name += "_TRY"
        return env_var_name

    def auth_token(self, try_storage: bool) -> str:
        env_var_name = self.env_var_name(try_storage)
        try:
            return os.environ[env_var_name]
        except KeyError:
            kind = "try" if try_storage else "regular"
            raise AuthTokenMissing(
                f"environment variable {env_var_name} for {kind} uploads not set"
            ) from None


FILE_NAME_PREFIX = "tecken-system-tests-"


class Random(random.Random):
    def hex_str(self, length: int) -> str:
        return self.randbytes((length + 1) // 2)[:length].hex()


class FakeSymFile:
    DEBUG_FILE_EXTENSIONS = {
        "linux": ".so",
        "mac": ".dylib",
        "windows": ".pdb",
    }
    NONSENSE_DIRECTIVES = [
        "FLIBBERWOCK",
        "ZINDLEFUMP",
        "GRUMBLETOCK",
        "SNORFLEQUIN",
        "WIBBLESNATCH",
        "BLORPTANGLE",
    ]

    def __init__(self, size: int, platform: str, seed: Optional[int] = None):
        self.size = size
        self.platform = platform
        self.seed = seed or random.getrandbits(64)

        rng = Random(self.seed)
        self.arch = rng.choice(["aarch64", "x86", "x86_64"])
        self.debug_id = rng.hex_str(33).upper()
        self.debug_file = (
            FILE_NAME_PREFIX
            + rng.hex_str(16)
            + self.DEBUG_FILE_EXTENSIONS[self.platform]
        )
        self.sym_file = self.debug_file.removesuffix(".pdb") + ".sym"
        if self.platform == "windows":
            self.code_file = self.debug_file.removesuffix(".pdb") + ".dll"
        else:
            self.code_file = ""
        self.code_id = rng.hex_str(16).upper()
        self.build_id = datetime.now().strftime("%Y%m%d%H%M%S")

    def key(self) -> str:
        return f"{self.debug_file}/{self.debug_id}/{self.sym_file}"

    def code_info_key(self) -> str:
        return f"{self.code_file}/{self.code_id}/{self.sym_file}"

    def header(self) -> bytes:
        return textwrap.dedent(f"""\
            MODULE {self.platform} {self.arch} {self.debug_id} {self.debug_file}
            INFO CODE_ID {self.code_id} {self.code_file}
            INFO RELEASECHANNEL nightly
            INFO VERSION 130.0
            INFO VENDOR Mozilla
            INFO PRODUCTNAME Firefox
            INFO BUILDID {self.build_id}
            INFO GENERATOR tecken-system-tests 1.0
            """).encode()

    def write(self, file: BinaryIO):
        header = self.header()
        file.write(header)
        written = len(header)
        rng = Random(self.seed)
        while written < self.size:
            line = f"{rng.choice(self.NONSENSE_DIRECTIVES)} {rng.hex_str(16_384)}\n".encode()
            file.write(line)
            written += len(line)


def _format_file_size(size: int) -> str:
    for factor, unit in [(2**30, "GiB"), (2**20, "MiB"), (2**10, "KiB")]:
        if size >= factor:
            return f"{size / factor:.1f} {unit}"
    return f"{size} bytes"


class FakeZipArchive:
    def __init__(
        self, size: int, sym_file_size: int, platform: str, seed: Optional[int] = None
    ):
        self.size = size
        self.sym_file_size = sym_file_size
        self.platform = platform
        self.seed = seed or random.getrandbits(64)

        self.file_name: Optional[str] = None
        self.members: list[FakeSymFile] = []
        self.uploaded = False

    def create(self, tmp_dir: os.PathLike):
        LOGGER.info(
            "Generating zip archive with a size of %s", _format_file_size(self.size)
        )
        rng = Random(self.seed)
        self.file_name = os.path.join(
            tmp_dir, FILE_NAME_PREFIX + rng.hex_str(16) + ".zip"
        )
        with open(self.file_name, "wb") as f:
            with zipfile.ZipFile(f, "w", compression=zipfile.ZIP_DEFLATED) as zip:
                while f.tell() < self.size:
                    sym_file = FakeSymFile(
                        self.sym_file_size, self.platform, seed=rng.getrandbits(64)
                    )
                    self.members.append(sym_file)
                    with NamedTemporaryFile() as sym_f:
                        sym_file.write(sym_f)
                        zip.write(sym_f.name, sym_file.key())


class TeckenRetry(Retry):
    """Retry class with customized backoff behavior and logging."""

    def get_backoff_time(self) -> float:
        # The standard Retry class uses a delay of 0 between the first and second attempt,
        # and exponential backoff after that.  We mostly need the retry behaviour for 429s,
        # so we should already wait after the first attempt, and we don't need exponential
        # backoff.
        if self.history and self.history[-1].status in self.status_forcelist:
            LOGGER.info("sleeping for 30 seconds...")
            return 30.0
        return 0.0

    def increment(self, *args, response=None, **kwargs) -> "TeckenRetry":
        if response and response.status >= 400:
            LOGGER.warning("response status code %s", response.status)
        return super().increment(*args, response=response, **kwargs)


class TeckenClient:
    def __init__(self, target_env: "Environment"):
        self.target_env = target_env
        self.base_url = target_env.base_url.removesuffix("/")
        self.session = Session()
        self.session.headers["User-Agent"] = "tecken-upload-loadtest-locust/1.0"
        retry = TeckenRetry(
            status=3, status_forcelist=[429, 502, 503, 504], allowed_methods=[]
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def auth_request(
        self,
        method: str,
        path: str,
        try_storage: bool = False,
        auth_token: Optional[str] = None,
        **kwargs,
    ) -> Response:
        if not auth_token:
            auth_token = self.target_env.auth_token(try_storage)
        headers = {"Auth-Token": auth_token}
        url = f"{self.base_url}{path}"
        return self.session.request(method, url, headers=headers, **kwargs)

    def upload(self, file_name: os.PathLike, try_storage: bool = False) -> Response:
        LOGGER.info("uploading %s", file_name)
        with open(file_name, "rb") as f:
            files = {os.path.basename(file_name): f}
            return self.auth_request("POST", "/upload/", try_storage, files=files)


@events.init.add_listener
def system_setup(environment, **kwargs):
    """Set up test system."""
    pass


class WebsiteUser(HttpUser):
    # wait_time = between(5, 15)

    @task
    def symbolicate(self):
        env = Environment(name=TARGET_ENV, base_url=HOST)
        with TemporaryDirectory() as tmp_dir:
            zip_archive = FakeZipArchive(
                size=ARCHIVE_SIZE,
                sym_file_size=SYM_SIZE,
                platform="windows",
            )
            zip_archive.create(tmp_dir=tmp_dir)

            t = time.time()
            with open(zip_archive.file_name, "rb") as fp:
                headers = {
                    "User-Agent": "tecken-upload-loadtest/1.0",
                    "Auth-Token": env.auth_token(try_storage=False),
                }
                files = {os.path.basename(zip_archive.file_name): fp}

                resp = self.client.post(
                    "/upload/", headers=headers, timeout=TIMEOUT, files=files
                )

                end_t = time.time()

                delta_t = int(end_t - t)
                assert (
                    resp.status_code == 201
                ), f"failed with {resp.status_code}: ({delta_t:,}s)"
