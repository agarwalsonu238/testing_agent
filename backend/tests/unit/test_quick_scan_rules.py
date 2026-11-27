from app.integrations.browser import PageObservation, RequestRecord, RouteDecision
from app.schemas.qa_config import Limits
from app.services.qa_config import compile_noise
from app.services.quick_scan import discoverable_paths, observations_to_findings, page_name

LIMITS = Limits(slow_api_ms=2000, slow_page_ms=5000)
NOISE = compile_noise([r"\[HMR\]", "webpack-hmr"])


def _obs(**kwargs: object) -> PageObservation:
    base = PageObservation(
        page_path="/pricing", page_name="Pricing", viewport="mobile", url="http://x/pricing"
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


def _titles(obs: PageObservation) -> dict[str, str]:
    return {f.title: f.severity for f in observations_to_findings(obs, LIMITS, NOISE)}


def test_clean_page_has_no_findings() -> None:
    assert observations_to_findings(_obs(main_status=200, load_ms=800), LIMITS, NOISE) == []


def test_api_500_is_high_and_4xx_is_medium() -> None:
    obs = _obs(
        requests=[
            RequestRecord(
                url="http://x/api/plans?id=1", method="GET", resource_type="fetch", status=500
            ),
            RequestRecord(url="http://x/api/me", method="GET", resource_type="fetch", status=404),
        ]
    )
    assert _titles(obs) == {
        "API call answered 500: GET /api/plans": "High",
        "API call answered 404: GET /api/me": "Medium",
    }


def test_failed_request_is_high_but_guard_blocks_are_not_findings() -> None:
    obs = _obs(
        requests=[
            RequestRecord(
                url="http://x/api/a", method="GET", resource_type="xhr", failure="net::ERR_FAILED"
            ),
            RequestRecord(
                url="http://x/api/pay",
                method="POST",
                resource_type="fetch",
                failure="net::ERR_BLOCKED_BY_CLIENT",
            ),
        ]
    )
    assert _titles(obs) == {"API call failed: GET /api/a": "High"}


def test_slow_api_and_slow_page_are_warnings() -> None:
    obs = _obs(
        load_ms=7000,
        requests=[
            RequestRecord(
                url="http://x/api/s",
                method="GET",
                resource_type="fetch",
                status=200,
                duration_ms=2500,
            )
        ],
    )
    assert _titles(obs) == {"Slow API call: GET /api/s": "Warning", "Slow page: Pricing": "Warning"}


def test_noise_filter_drops_dev_server_messages() -> None:
    obs = _obs(
        console_errors=[
            "[HMR] connected",
            "TypeError: x is undefined",
            "TypeError: x is undefined",
            "Failed to load resource: the server responded with a status of 404 ()",
        ],
        requests=[
            RequestRecord(
                url="http://x/_next/webpack-hmr",
                method="GET",
                resource_type="fetch",
                failure="aborted",
            )
        ],
    )
    findings = observations_to_findings(obs, LIMITS, NOISE)
    assert [f.title for f in findings] == ["Console error: TypeError: x is undefined"]
    assert findings[0].severity == "Medium"


def test_mobile_overflow_broken_image_and_page_error() -> None:
    obs = _obs(
        overflow_px=120,
        broken_images=["http://x/img/hero.png"],
        page_errors=["ReferenceError: foo is not defined\n at bar"],
    )
    assert _titles(obs) == {
        "Page is wider than a phone screen": "Medium",
        "Broken image: /img/hero.png": "Medium",
        "Uncaught error: ReferenceError: foo is not defined": "High",
    }


def test_navigation_error_is_environment_when_app_is_down() -> None:
    findings = observations_to_findings(
        _obs(nav_error="net::ERR_CONNECTION_REFUSED at http://x/pricing"), LIMITS, NOISE
    )
    assert len(findings) == 1
    assert findings[0].severity == "High"
    assert findings[0].category == "environment"


def test_findings_carry_location_and_screenshot() -> None:
    findings = observations_to_findings(
        _obs(main_status=503), LIMITS, NOISE, screenshot_rel="screenshots/pricing-mobile.png"
    )
    assert findings[0].location == "/pricing · mobile"
    assert findings[0].evidence[-1].path == "screenshots/pricing-mobile.png"


def _allow(url: str, method: str) -> RouteDecision | None:
    return None


def test_discoverable_paths_keeps_same_site_pages_once_in_order() -> None:
    links = [
        "https://app.example.test/pricing",
        "https://app.example.test/pricing?plan=pro",
        "https://app.example.test/pricing#faq",
        "https://app.example.test/",
        "https://other.example.test/blog",
        "mailto:hi@example.test",
        "https://app.example.test/logout",
        "https://app.example.test/terms.pdf",
        "https://app.example.test/how-it-works",
    ]
    paths = discoverable_paths(links, "https://app.example.test", _allow)
    assert paths == ["/pricing", "/", "/how-it-works"]


def test_discoverable_paths_skips_what_the_guard_would_block() -> None:
    def block_admin(url: str, method: str) -> RouteDecision | None:
        return RouteDecision(kind="block", label="risky") if "/admin" in url else None

    links = ["https://app.example.test/admin/users", "https://app.example.test/faq"]
    assert discoverable_paths(links, "https://app.example.test/", block_admin) == ["/faq"]


def test_page_name_reads_the_last_path_segment() -> None:
    assert page_name("/") == "Home"
    assert page_name("/how-it-works") == "How it works"
    assert page_name("/docs/getting_started/") == "Getting started"
