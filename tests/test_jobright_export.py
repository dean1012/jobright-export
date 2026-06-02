import http.client
import io
import json
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stderr, redirect_stdout
from email.message import Message
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

MODULE_PATH = Path(__file__).parents[1] / "jobright-export"
jobright_export = ModuleType("jobright_export")
SourceFileLoader(jobright_export.__name__, str(MODULE_PATH)).exec_module(
    jobright_export
)

VALID_URL = "https://jobright.ai/jobs/info/abc123"
VALID_JOB = {
    "isDeleted": False,
    "isRemote": False,
    "jobLocation": "Houston, TX, US",
    "jobTitle": "Platform Engineer",
    "workModel": "hybrid",
}
VALID_COMPANY = {"companyName": "Example Systems"}


def make_headers() -> Message:
    return Message()


def make_payload(
    job_result: dict[str, object] | None = None,
    company_result: dict[str, object] | None = None,
) -> bytes:
    payload = {
        "jobResult": VALID_JOB if job_result is None else job_result,
        "companyResult": VALID_COMPANY if company_result is None else company_result,
    }
    return (
        '<html><script id="jobright-helper-job-detail-info">'
        f"{json.dumps(payload)}"
        "</script></html>"
    ).encode()


class FakeResponse:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = iter(chunks)
        self.read_count = 0

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _size: int) -> bytes:
        self.read_count += 1
        return next(self.chunks, b"")


class UrlTests(unittest.TestCase):
    def test_accepts_expected_url_variations(self) -> None:
        urls = (
            VALID_URL,
            f"{VALID_URL}/",
            f"{VALID_URL}?source=test#details",
            "https://www.jobright.ai/jobs/info/abc_123-XYZ",
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertTrue(jobright_export.valid_jobright_url(url))

    def test_rejects_unexpected_urls(self) -> None:
        urls = (
            "",
            "asdf",
            "http://jobright.ai/jobs/info/abc123",
            "https://example.com/jobs/info/abc123",
            "https://jobright.ai.example.com/jobs/info/abc123",
            "https://user@jobright.ai/jobs/info/abc123",
            "https://jobright.ai:443/jobs/info/abc123",
            "https://jobright.ai/jobs/info/",
            "https://jobright.ai/jobs/info/abc123/extra",
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertFalse(jobright_export.valid_jobright_url(url))

    def test_canonicalizes_expected_url(self) -> None:
        url = "https://www.jobright.ai/jobs/info/abc123/?source=test#details"

        self.assertEqual(jobright_export.canonicalize_jobright_url(url), VALID_URL)

    def test_rejects_invalid_url_during_canonicalization(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid Jobright.ai"):
            jobright_export.canonicalize_jobright_url("https://example.com")


class RedirectTests(unittest.TestCase):
    def test_allows_redirect_to_same_canonical_job_url(self) -> None:
        handler = jobright_export.JobrightRedirectHandler()
        request = urllib.request.Request(VALID_URL)  # noqa: S310 - Allow-listed URL.

        redirected_request = handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            f"{VALID_URL}/?source=test",
        )

        self.assertIsNotNone(redirected_request)
        self.assertEqual(redirected_request.full_url, VALID_URL)

    def test_rejects_redirect_to_different_job_url(self) -> None:
        handler = jobright_export.JobrightRedirectHandler()
        request = urllib.request.Request(VALID_URL)  # noqa: S310 - Allow-listed URL.

        with self.assertRaisesRegex(urllib.error.HTTPError, "unexpected URL"):
            handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                "https://jobright.ai/jobs/info/different-job",
            )

    def test_rejects_redirect_to_different_host(self) -> None:
        handler = jobright_export.JobrightRedirectHandler()
        request = urllib.request.Request(VALID_URL)  # noqa: S310 - Allow-listed URL.

        with self.assertRaisesRegex(urllib.error.HTTPError, "unexpected URL"):
            handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                "https://example.com/jobs/info/abc123",
            )


class PayloadParserTests(unittest.TestCase):
    def test_extracts_embedded_payload_split_across_chunks(self) -> None:
        parser = jobright_export.JobrightPayloadParser()
        payload = make_payload()
        midpoint = len(payload) // 2

        parser.feed(payload[:midpoint].decode())
        parser.feed(payload[midpoint:].decode())

        self.assertEqual(
            jobright_export.extract_job_data(parser),
            (VALID_JOB, VALID_COMPANY),
        )

    def test_rejects_page_without_payload(self) -> None:
        parser = jobright_export.JobrightPayloadParser()
        parser.feed("<html></html>")

        with self.assertRaises(jobright_export.InvalidJobPostingError):
            jobright_export.extract_job_data(parser)

    def test_rejects_payload_without_required_results(self) -> None:
        parser = jobright_export.JobrightPayloadParser()
        parser.feed(
            '<script id="jobright-helper-job-detail-info">{"jobResult": {}}</script>'
        )

        with self.assertRaises(jobright_export.InvalidJobPostingError):
            jobright_export.extract_job_data(parser)


class FetchTests(unittest.TestCase):
    def fetch_with_response(
        self,
        response: FakeResponse,
    ) -> tuple[dict[str, object], dict[str, object]]:
        opener = Mock()
        opener.open.return_value = response

        with patch.object(
            jobright_export.urllib.request,
            "build_opener",
            return_value=opener,
        ):
            return jobright_export.fetch_job_data(VALID_URL)

    def test_stops_reading_after_complete_payload(self) -> None:
        response = FakeResponse([make_payload(), b"unnecessary trailing content"])

        self.assertEqual(
            self.fetch_with_response(response),
            (VALID_JOB, VALID_COMPANY),
        )
        self.assertEqual(response.read_count, 1)

    def test_rejects_response_that_exceeds_scan_limit(self) -> None:
        response = FakeResponse([b"x" * 11])

        with (
            patch.object(jobright_export, "MAX_BYTES_TO_SCAN", 10),
            self.assertRaises(jobright_export.ResponseTooLargeError),
        ):
            self.fetch_with_response(response)

    def test_maps_server_error_to_site_unavailable(self) -> None:
        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError(
            VALID_URL,
            500,
            "Internal Server Error",
            make_headers(),
            None,
        )

        with (
            patch.object(
                jobright_export.urllib.request,
                "build_opener",
                return_value=opener,
            ),
            self.assertRaises(jobright_export.SiteUnavailableError),
        ):
            jobright_export.fetch_job_data(VALID_URL)

    def test_maps_connection_error_to_site_unavailable(self) -> None:
        opener = Mock()
        opener.open.side_effect = http.client.RemoteDisconnected(
            "Remote end closed connection"
        )

        with (
            patch.object(
                jobright_export.urllib.request,
                "build_opener",
                return_value=opener,
            ),
            self.assertRaises(jobright_export.SiteUnavailableError),
        ):
            jobright_export.fetch_job_data(VALID_URL)

    def test_maps_not_found_to_invalid_posting(self) -> None:
        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError(
            VALID_URL,
            404,
            "Not Found",
            make_headers(),
            None,
        )

        with (
            patch.object(
                jobright_export.urllib.request,
                "build_opener",
                return_value=opener,
            ),
            self.assertRaises(jobright_export.InvalidJobPostingError),
        ):
            jobright_export.fetch_job_data(VALID_URL)


class FormattingTests(unittest.TestCase):
    def test_validates_required_job_fields(self) -> None:
        self.assertTrue(jobright_export.valid_job_posting(VALID_JOB, VALID_COMPANY))

        invalid_jobs = (
            {**VALID_JOB, "isDeleted": True},
            {**VALID_JOB, "isRemote": "false"},
            {**VALID_JOB, "jobLocation": ""},
            {**VALID_JOB, "workModel": "undefined"},
            {**VALID_JOB, "jobTitle": ""},
        )

        for job_result in invalid_jobs:
            with self.subTest(job_result=job_result):
                self.assertFalse(
                    jobright_export.valid_job_posting(job_result, VALID_COMPANY)
                )

    def test_accepts_remote_posting_without_location(self) -> None:
        job_result = {
            "isRemote": True,
            "jobTitle": "Cloud Engineer",
        }

        self.assertTrue(jobright_export.valid_job_posting(job_result, VALID_COMPANY))

    def test_sanitizes_spreadsheet_value(self) -> None:
        self.assertEqual(
            jobright_export.spreadsheet_safe("  =SUM(A1)\r\n\t"),
            "'  =SUM(A1)   ",
        )

    def test_escapes_spreadsheet_formula_prefixes(self) -> None:
        values = (
            "=SUM(A1:A2)",
            "+1+1",
            "-1+1",
            "@SUM(A1:A2)",
        )

        for value in values:
            with self.subTest(value=value):
                self.assertEqual(
                    jobright_export.spreadsheet_safe(f"  {value}"),
                    f"'  {value}",
                )

    def test_formats_us_location_with_state_code(self) -> None:
        self.assertEqual(
            jobright_export.format_location("Houston, TX, US", "hybrid"),
            "Houston, TX Hybrid",
        )

    def test_formats_us_location_with_state_name(self) -> None:
        self.assertEqual(
            jobright_export.format_location(
                "Houston, Texas, United States",
                "onsite",
            ),
            "Houston, Texas Onsite",
        )

    def test_preserves_unfamiliar_location(self) -> None:
        self.assertEqual(
            jobright_export.format_location("Toronto, ON, Canada", "hybrid"),
            "Toronto, ON, Canada Hybrid",
        )

    def test_parses_remote_posting(self) -> None:
        job_result = {
            "isRemote": True,
            "jobTitle": "Cloud Engineer",
        }

        self.assertEqual(
            jobright_export.parse_jobright(job_result, VALID_COMPANY, VALID_URL),
            f"Example Systems\tCloud Engineer\tRemote\t{VALID_URL}",
        )

    def test_sanitizes_each_parsed_field(self) -> None:
        job_result = {
            "isRemote": False,
            "jobLocation": "Austin,\nTX",
            "jobTitle": "=IMPORTXML()",
            "workModel": "onsite",
        }
        company_result = {"companyName": "Example\tSystems"}

        self.assertEqual(
            jobright_export.parse_jobright(job_result, company_result, VALID_URL),
            f"Example Systems\t'=IMPORTXML()\tAustin, TX Onsite\t{VALID_URL}",
        )


class MainTests(unittest.TestCase):
    def run_main(self, inputs: list[str]) -> tuple[str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch("builtins.input", side_effect=inputs),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            jobright_export.main()

        return stdout.getvalue(), stderr.getvalue()

    def test_prompts_again_after_blank_and_invalid_urls(self) -> None:
        stdout, _stderr = self.run_main(["", "asdf", "exit"])

        self.assertIn("Invalid URL.", stdout)

    def test_reports_deleted_posting_and_prompts_again(self) -> None:
        deleted_job = {**VALID_JOB, "isDeleted": True}

        with patch.object(
            jobright_export,
            "fetch_job_data",
            return_value=(deleted_job, VALID_COMPANY),
        ):
            stdout, _stderr = self.run_main([VALID_URL, "quit"])

        self.assertIn("This jobright.ai job posting has been deleted.", stdout)

    def test_reports_site_unavailable_and_prompts_again(self) -> None:
        with patch.object(
            jobright_export,
            "fetch_job_data",
            side_effect=jobright_export.SiteUnavailableError,
        ):
            _stdout, stderr = self.run_main([VALID_URL, "quit"])

        self.assertIn("site cannot be reached at this time", stderr)

    def test_displays_result_when_clipboard_copy_fails(self) -> None:
        with (
            patch.object(
                jobright_export,
                "fetch_job_data",
                return_value=(VALID_JOB, VALID_COMPANY),
            ),
            patch.object(
                jobright_export.pyperclip,
                "copy",
                side_effect=jobright_export.pyperclip.PyperclipException,
            ),
        ):
            stdout, stderr = self.run_main([VALID_URL, "quit"])

        self.assertIn(
            f"Example Systems\tPlatform Engineer\tHouston, TX Hybrid\t{VALID_URL}",
            stdout,
        )
        self.assertIn("Could not copy to the clipboard", stderr)


if __name__ == "__main__":
    unittest.main()
