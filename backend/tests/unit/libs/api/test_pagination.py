"""libs.api.pagination 单测。"""

from __future__ import annotations

from libs.api.pagination import PageParams, build_page, slice_page, total_pages


def test_page_params_offset() -> None:
    assert PageParams(page=1, page_size=20).offset == 0
    assert PageParams(page=3, page_size=50).offset == 100


def test_build_page_has_next_prev() -> None:
    page = build_page(items=["a", "b"], total=100, page=2, page_size=20)
    assert page.has_prev is True
    assert page.has_next is True
    assert page.page == 2
    assert page.total == 100


def test_build_page_last_page() -> None:
    page = build_page(items=["z"], total=41, page=3, page_size=20)
    assert page.has_next is False
    assert page.has_prev is True


def test_build_page_empty_total() -> None:
    page = build_page(items=[], total=0, page=1, page_size=20)
    assert page.has_next is False
    assert page.has_prev is False
    assert total_pages(0, 20) == 1


def test_slice_page() -> None:
    rows = list(range(10))
    items, total = slice_page(rows, page=2, page_size=3)
    assert total == 10
    assert items == [3, 4, 5]
