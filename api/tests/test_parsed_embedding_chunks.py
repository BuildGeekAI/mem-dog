"""Phase 2: parsed-body embedding chunk helpers."""

from app.storage import (
    _chunk_specs_from_parsed_json,
    _chunk_specs_from_text,
    _coalesce_chunk_specs,
    _expand_chunk_specs,
)


class TestChunkSpecsFromParsedJson:
    def test_preserves_page_metadata(self):
        doc = {
            "chunks": [
                {
                    "text": "Coverages on page one",
                    "page": 1,
                    "section_path": ["Page 1"],
                    "element_type": "narrative",
                },
                {
                    "text": "Deductible on page two",
                    "page": 2,
                    "section_path": ["Page 2"],
                    "element_type": "narrative",
                },
            ]
        }
        specs = _chunk_specs_from_parsed_json(doc, chunk_size=1000, chunk_overlap=200)
        assert len(specs) == 2
        assert specs[0]["page"] == 1
        assert specs[0]["section_path"] == ["Page 1"]
        assert specs[0]["embedding_kind"] == "body"
        assert specs[1]["page"] == 2
        assert "Deductible" in specs[1]["text"]

    def test_empty_chunks_returns_empty(self):
        assert _chunk_specs_from_parsed_json({}, 1000, 200) == []
        assert _chunk_specs_from_parsed_json({"chunks": []}, 1000, 200) == []

    def test_oversized_chunk_inherits_page(self):
        long = "x" * 2500
        specs = _expand_chunk_specs(
            [{"text": long, "page": 7, "section_path": ["Page 7"], "element_type": "narrative"}],
            chunk_size=1000,
            chunk_overlap=200,
        )
        assert len(specs) > 1
        assert all(s["page"] == 7 for s in specs)

    def test_coalesces_short_docx_paragraphs(self):
        doc = {
            "chunks": [
                {"text": "First paragraph.", "page": None, "section_path": [], "element_type": "narrative"},
                {"text": "Second paragraph.", "page": None, "section_path": [], "element_type": "narrative"},
                {"text": "Third paragraph.", "page": None, "section_path": [], "element_type": "narrative"},
            ]
        }
        specs = _chunk_specs_from_parsed_json(doc, chunk_size=1000, chunk_overlap=200)
        assert len(specs) == 1
        assert "First paragraph." in specs[0]["text"]
        assert "Third paragraph." in specs[0]["text"]
        assert specs[0]["page"] is None

    def test_does_not_merge_across_pages(self):
        specs = _coalesce_chunk_specs(
            [
                {"text": "a", "page": 1, "section_path": ["Page 1"], "element_type": "narrative"},
                {"text": "b", "page": 2, "section_path": ["Page 2"], "element_type": "narrative"},
            ],
            chunk_size=1000,
        )
        assert len(specs) == 2


class TestChunkSpecsFromText:
    def test_basic_split(self):
        specs = _chunk_specs_from_text("hello world", 1000, 200)
        assert len(specs) == 1
        assert specs[0]["page"] is None
        assert specs[0]["text"] == "hello world"
