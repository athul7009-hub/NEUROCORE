
from app.tools.duplicate_detector import find_duplicates


def test_find_duplicates():
    files = [
        {"path": "a.txt", "sha256": "abc"},
        {"path": "b.txt", "sha256": "abc"},
        {"path": "c.txt", "sha256": "xyz"},
    ]

    assert find_duplicates(files) == [["a.txt", "b.txt"]]


def test_no_duplicates():
    files = [
        {"path": "a.txt", "sha256": "abc"},
        {"path": "b.txt", "sha256": "xyz"},
    ]

    assert find_duplicates(files) == []


def test_empty_input():
    assert find_duplicates([]) == []
