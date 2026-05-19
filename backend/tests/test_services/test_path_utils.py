import pytest

from app.core.exceptions import BadRequestException
from app.utils.path_utils import normalize_path, safe_upload_filename


def test_normalize_path_rejects_parent_segments():
    with pytest.raises(BadRequestException):
        normalize_path("/safe/../secret.txt")


def test_normalize_path_rejects_null_byte():
    with pytest.raises(BadRequestException):
        normalize_path("/safe/\x00.txt")


def test_safe_upload_filename_rejects_path_components():
    for filename in ("../secret.txt", "nested/file.txt", r"nested\file.txt"):
        with pytest.raises(BadRequestException):
            safe_upload_filename(filename)


def test_safe_upload_filename_accepts_plain_filename():
    assert safe_upload_filename("report.txt") == "report.txt"
