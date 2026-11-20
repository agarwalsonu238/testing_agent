from app.services.api_reference import (
    compare,
    extract_urls,
    fields_of,
    main_list,
    total_of,
    with_param,
)

PLAIN = {"data": [{"id": 1}, {"id": 2}, {"id": 3}], "pagination": {"page": 1, "total": 120}}


def test_extract_urls_dedupes_and_skips_link_local() -> None:
    task = (
        "check https://a.example.com/api/v1/products/?page=2. "
        "and http://169.254.169.254/x https://a.example.com/api/v1/products/?page=2"
    )
    assert extract_urls(task) == ["https://a.example.com/api/v1/products/?page=2"]


def test_fields_lists_every_key_with_types() -> None:
    fields = {
        f.key: f.type
        for f in fields_of(
            {"data": [{"id": "a", "price": 5, "tag": None}, {"id": "b", "tag": "x"}]}
        )
    }
    assert fields["data[].id"] == "string"
    assert fields["data[].price"] == "integer"
    assert fields["data[].tag"] == "null or string"


def test_main_list_and_total_found_in_a_wrapped_response() -> None:
    assert main_list(PLAIN) == PLAIN["data"]
    assert total_of(PLAIN) == 120


def test_compare_detects_filter_order_and_no_effect() -> None:
    fewer = {"data": [{"id": 1}], "pagination": {"total": 1}}
    reordered = {"data": [{"id": 3}, {"id": 2}, {"id": 1}], "pagination": {"total": 120}}
    assert compare(PLAIN, fewer) == ("changes result", "3 to 1 items, total 120 to 1")
    assert compare(PLAIN, reordered)[0] == "changes order"
    assert compare(PLAIN, PLAIN)[0] == "no visible effect"


def test_with_param_replaces_an_existing_value() -> None:
    assert with_param("https://a.com/p?page=1&x=y", "page", "2") == "https://a.com/p?x=y&page=2"
