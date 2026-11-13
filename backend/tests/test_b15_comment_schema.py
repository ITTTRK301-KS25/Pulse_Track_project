"""B15: DTO bình luận (không cần DB)."""
import importlib.util, json, sys
from pathlib import Path
import pytest
from pydantic import ValidationError

p = Path(__file__).resolve().parents[1] / "app/schemas/comment.py"
spec = importlib.util.spec_from_file_location("comment_schema_t", p)
m = importlib.util.module_from_spec(spec); sys.modules["comment_schema_t"] = m; spec.loader.exec_module(m)
Create = m.CreateCommentRequest


def test_trim_and_keep_text():
    assert Create(content="  Xong phần API  ").content == "Xong phần API"


def test_empty_or_blank_rejected():
    for bad in ("", "   ", "\n\t "):
        with pytest.raises(ValidationError):
            Create(content=bad)


def test_length_bounds():
    assert Create(content="x" * 2000)
    with pytest.raises(ValidationError):
        Create(content="x" * 2001)


def test_line_breaks_normalized_and_control_chars_removed():
    assert Create(content="a\r\nb\rc").content == "a\nb\nc"
    assert Create(content="a\x00b\x07c").content == "abc"


def test_html_is_stored_as_text_not_executed():
    s = "<script>alert(1)</script>"
    assert Create(content=s).content == s   # lưu nguyên văn; frontend dùng textContent


def test_missing_content():
    with pytest.raises(ValidationError):
        Create()


def test_errors_json_serializable():
    with pytest.raises(ValidationError) as e:
        Create(content="")
    json.dumps(e.value.errors(include_url=False))
