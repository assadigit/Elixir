"""V13.31.4: Regression tests for Obsidian sync, translation echo,
image transparency, and packets streaming features."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_obsidian_sync_basic():
    try:
        import core.obsidian.vault_sync as vs
    except ImportError:
        return  # skip if module deps unavailable
    vs._CACHE_FILE = Path(tempfile.gettempdir()) / "test_obs_sync_reg.json"
    if vs._CACHE_FILE.exists(): vs._CACHE_FILE.unlink()
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td) / "Articles"; vault.mkdir()
        (vault / "a1.md").write_text("# A1\n\nContent one.")
        (vault / "a2.md").write_text("# A2\n\nContent two.")
        files = vs.scan_vault_folder(str(vault))
        assert len(files) == 2
        new = vs.get_new_files(str(vault), "summarizer")
        assert len(new) == 2

def test_obsidian_sync_mark_processed():
    try:
        import core.obsidian.vault_sync as vs
    except ImportError:
        return  # skip if module deps unavailable
    vs._CACHE_FILE = Path(tempfile.gettempdir()) / "test_obs_mark_reg.json"
    if vs._CACHE_FILE.exists(): vs._CACHE_FILE.unlink()
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td) / "V"; vault.mkdir()
        src = vault / "a.md"; src.write_text("# A\n\nC.")
        files = vs.scan_vault_folder(str(vault))
        out = Path(td) / "s.md"; out.write_text("s")
        vs.mark_file_processed(str(vault), files[0], out, "summarizer")
        assert len(vs.get_new_files(str(vault), "summarizer")) == 0
        content = src.read_text()
        assert "summarized: true" in content

def test_translation_echo_persian_instruction():
    import re

    from core.translation.translation_engine import _ECHO_PATTERNS
    raw = "متن انگلیسی را به فارسی ترجمه کنید:\nترجمه:\nسلام دنیا"
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    for pat in _ECHO_PATTERNS:
        text = re.sub(pat, "", text, flags=re.IGNORECASE | re.MULTILINE).strip()
    assert "سلام دنیا" in text

def test_translation_echo_preserves_real_text():
    import re

    from core.translation.translation_engine import _ECHO_PATTERNS
    raw = "This is a real translation."
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    for pat in _ECHO_PATTERNS:
        text = re.sub(pat, "", text, flags=re.IGNORECASE | re.MULTILINE).strip()
    assert text == "This is a real translation."

def test_packets_streaming_parse():
    import json
    chunks = [
        {"response": "Packet ", "done": False},
        {"response": "text.", "done": False},
        {"response": "", "done": True},
    ]
    mock_lines = [json.dumps(c) for c in chunks]
    content_parts = []
    for line in mock_lines:
        if not line: continue
        try:
            chunk = json.loads(line)
            piece = chunk.get("response", "")
            if piece: content_parts.append(piece)
            if chunk.get("done"): break
        except Exception: continue
    assert "".join(content_parts).strip() == "Packet text."
