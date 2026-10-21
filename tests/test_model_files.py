import pytest
from helper import find_model_files

def test_lists_only_pt_files(tmp_path):
    (tmp_path / "b.pt").write_text("x")
    (tmp_path / "a.pt").write_text("x")
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path / "sub").mkdir()
    assert find_model_files(str(tmp_path)) == ["a.pt", "b.pt"]

def test_missing_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_model_files(str(tmp_path / "nope"))

def test_empty_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_model_files(str(tmp_path))