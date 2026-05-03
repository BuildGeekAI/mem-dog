"""Unit tests for url_context (get_urls_to_download, fetch_url_bytes)."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def url_context_mod():
    import webhook.processor.webhook_agent.url_context as url_context
    return url_context


class TestGetUrlsToDownload:
    """get_urls_to_download: resolve URL to single direct file or list of links from page."""

    def test_empty_url_returns_empty_list(self, url_context_mod):
        """Empty or missing url → []."""
        assert url_context_mod.get_urls_to_download("") == []
        assert url_context_mod.get_urls_to_download(None) == []

    def test_non_http_url_returns_empty_list(self, url_context_mod):
        """Non-http(s) URL → []."""
        assert url_context_mod.get_urls_to_download("ftp://example.com/f") == []
        assert url_context_mod.get_urls_to_download("file:///local/path") == []

    def test_direct_file_attachment_returns_single_url(self, url_context_mod):
        """Response with Content-Disposition: attachment → [url] (direct file)."""
        url = "https://example.com/file.pdf"

        def header_get(key, default=None):
            if key == "Content-Type":
                return "application/pdf"
            if key == "Content-Disposition":
                return "attachment; filename=file.pdf"
            return default

        mock_resp = MagicMock()
        mock_resp.headers = MagicMock()
        mock_resp.headers.get = header_get
        mock_resp.raise_for_status = MagicMock()
        with patch.object(url_context_mod, "_session") as mock_session:
            mock_session.get.return_value = mock_resp
            result = url_context_mod.get_urls_to_download(url)
        assert result == [url]
        mock_resp.close.assert_called_once()

    def test_direct_file_non_html_content_type_returns_single_url(self, url_context_mod):
        """Response with non-HTML Content-Type (e.g. application/pdf) → [url]."""
        url = "https://example.com/file.pdf"

        def header_get(key, default=None):
            if key == "Content-Type":
                return "application/pdf"
            if key == "Content-Disposition":
                return None
            return default

        mock_resp = MagicMock()
        mock_resp.headers = MagicMock()
        mock_resp.headers.get = header_get
        mock_resp.raise_for_status = MagicMock()
        with patch.object(url_context_mod, "_session") as mock_session:
            mock_session.get.return_value = mock_resp
            result = url_context_mod.get_urls_to_download(url)
        assert result == [url]
        mock_resp.close.assert_called_once()

    def test_html_page_extracts_links(self, url_context_mod):
        """Response with Content-Type: text/html and <a href> → list of absolute URLs."""
        url = "https://example.com/page.html"
        html = '<html><body><a href="/file.pdf">PDF</a><a href="https://other.com/x.pdf">Other</a></body></html>'

        def header_get(key, default=None):
            if key == "Content-Type":
                return "text/html"
            if key == "Content-Disposition":
                return None
            return default

        mock_resp = MagicMock()
        mock_resp.headers = MagicMock()
        mock_resp.headers.get = header_get
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_content = lambda chunk_size: [html.encode("utf-8")]
        mock_resp.close = MagicMock()

        with patch.object(url_context_mod, "_session") as mock_session:
            mock_session.get.return_value = mock_resp
            result = url_context_mod.get_urls_to_download(url)

        assert len(result) == 2
        assert "file.pdf" in result[0]
        assert result[0].startswith("https://example.com/")
        assert result[1] == "https://other.com/x.pdf"

    def test_prompt_document_filters_to_document_extensions(self, url_context_mod):
        """With prompt containing 'document', only URLs with document-like extensions are returned."""
        url = "https://example.com/page.html"
        html = (
            '<html><body>'
            '<a href="/file.pdf">PDF</a>'
            '<a href="/image.png">Image</a>'
            '<a href="/doc.docx">Doc</a>'
            '</body></html>'
        )

        def header_get(key, default=None):
            if key == "Content-Type":
                return "text/html"
            if key == "Content-Disposition":
                return None
            return default

        mock_resp = MagicMock()
        mock_resp.headers = MagicMock()
        mock_resp.headers.get = header_get
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_content = lambda chunk_size: [html.encode("utf-8")]
        mock_resp.close = MagicMock()

        with patch.object(url_context_mod, "_session") as mock_session:
            mock_session.get.return_value = mock_resp
            result = url_context_mod.get_urls_to_download(url, prompt="download all document files")

        assert len(result) == 2
        assert any("file.pdf" in u for u in result)
        assert any("doc.docx" in u for u in result)
        assert not any("image.png" in u for u in result)


class TestFetchUrlBytes:
    """fetch_url_bytes: download content and return (bytes, content_type)."""

    def test_returns_content_and_content_type(self, url_context_mod):
        """Successful GET → (bytes, content_type)."""
        url = "https://example.com/file.pdf"
        mock_resp = MagicMock()
        mock_resp.content = b"fake-pdf-bytes"
        mock_resp.headers.get.return_value = "application/pdf"
        mock_resp.raise_for_status = MagicMock()
        with patch.object(url_context_mod, "_session") as mock_session:
            mock_session.get.return_value = mock_resp
            content, content_type = url_context_mod.fetch_url_bytes(url)
        assert content == b"fake-pdf-bytes"
        assert content_type == "application/pdf"

    def test_uses_mime_type_hint_when_header_missing(self, url_context_mod):
        """When response has no Content-Type, mime_type_hint is used."""
        url = "https://example.com/file"
        mock_resp = MagicMock()
        mock_resp.content = b"data"
        mock_resp.headers.get.return_value = None
        mock_resp.raise_for_status = MagicMock()
        with patch.object(url_context_mod, "_session") as mock_session:
            mock_session.get.return_value = mock_resp
            content, content_type = url_context_mod.fetch_url_bytes(url, mime_type_hint="application/octet-stream")
        assert content_type == "application/octet-stream"
