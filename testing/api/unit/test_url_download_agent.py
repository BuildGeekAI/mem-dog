"""Unit tests for UrlDownloadAgent (Layer 0b download sub-agent)."""

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def url_download_agent():
    from webhook.processor.webhook_agent.sub_agents.download.url_download import UrlDownloadAgent
    return UrlDownloadAgent()


class TestUrlDownloadAgentWriteRecord:
    """UrlDownloadAgent.write_record: resolve URL(s), download, upload, re-invoke pipeline."""

    def test_missing_url_returns_error(self, url_download_agent):
        """write_record with no url in meta or payload → error, no download/reinvoke."""
        result = url_download_agent.write_record("{}", meta_data={})
        assert result.get("status") == "error"
        assert "url" in (result.get("error_message") or "").lower()

    def test_invalid_url_returns_error(self, url_download_agent):
        """write_record with non-http url in meta → error."""
        result = url_download_agent.write_record(
            "{}",
            meta_data={"access": {"url": "ftp://example.com/f"}},
        )
        assert result.get("status") == "error"

    def test_valid_url_downloads_and_reinvokes_with_data_id_and_is_downloaded(self, url_download_agent):
        """write_record with valid url: get_urls_to_download returns one URL; upload and reinvoke once."""
        reinvoke_payloads = []

        def capture_route_payload(payload_json):
            reinvoke_payloads.append(json.loads(payload_json))

        with (
            patch(
                "webhook.processor.webhook_agent.sub_agents.download.url_download.get_urls_to_download",
                return_value=["https://example.com/file.pdf"],
            ),
            patch(
                "webhook.processor.webhook_agent.sub_agents.download.url_download.fetch_url_bytes",
                return_value=(b"fake-pdf-content", "application/pdf"),
            ),
            patch(
                "webhook.processor.webhook_agent.sub_agents.download.url_download.data_client",
            ) as mock_data_client,
            patch(
                "webhook.processor.webhook_agent.router.route_payload",
                side_effect=capture_route_payload,
            ),
        ):
            mock_data_client.create_from_bytes.return_value = {"data_id": "d-new-1", "version": 1}

            result = url_download_agent.write_record(
                "{}",
                meta_data={
                    "access": {"url": "https://example.com/file.pdf", "is_downloaded": False},
                    "identity": {"user_id": "alice"},
                },
            )

        assert result.get("status") == "success"
        assert result.get("data_id") == "d-new-1"
        assert len(reinvoke_payloads) == 1
        reinvoke_meta = reinvoke_payloads[0].get("meta_data", {})
        # Nested structure assertions
        assert reinvoke_meta.get("access", {}).get("data_id") == "d-new-1"
        assert reinvoke_meta.get("access", {}).get("is_downloaded") is True

    def test_prompt_passed_to_get_urls_to_download(self, url_download_agent):
        """write_record with url and meta_data['prompt'] → get_urls_to_download called with that prompt."""
        with (
            patch(
                "webhook.processor.webhook_agent.sub_agents.download.url_download.get_urls_to_download",
                return_value=["https://example.com/doc.pdf"],
            ) as mock_get_urls,
            patch(
                "webhook.processor.webhook_agent.sub_agents.download.url_download.fetch_url_bytes",
                return_value=(b"content", "application/pdf"),
            ),
            patch(
                "webhook.processor.webhook_agent.sub_agents.download.url_download.data_client",
            ),
            patch(
                "webhook.processor.webhook_agent.router.route_payload",
            ),
        ):
            url_download_agent.write_record(
                "{}",
                meta_data={
                    "access": {"url": "https://example.com/page.html", "is_downloaded": False},
                    "routing": {"prompt": "download all document files"},
                    "identity": {"user_id": "alice"},
                },
            )
            mock_get_urls.assert_called_once()
            args = mock_get_urls.call_args[0]
            assert args[0] == "https://example.com/page.html"
            assert args[1] == "download all document files"

    def test_empty_urls_list_returns_success_no_reinvoke(self, url_download_agent):
        """get_urls_to_download returns empty list → success with data_ids: [], no reinvoke."""
        with (
            patch(
                "webhook.processor.webhook_agent.sub_agents.download.url_download.get_urls_to_download",
                return_value=[],
            ),
        ):
            result = url_download_agent.write_record(
                "{}",
                meta_data={
                    "access": {"url": "https://example.com/empty-page.html", "is_downloaded": False},
                    "identity": {"user_id": "alice"},
                },
            )
        assert result.get("status") == "success"
        assert result.get("data_ids") == []
        assert "message" in result

    def test_all_downloads_or_uploads_fail_returns_error(self, url_download_agent):
        """When every fetch or create_from_bytes fails → error status, no reinvoke."""
        with (
            patch(
                "webhook.processor.webhook_agent.sub_agents.download.url_download.get_urls_to_download",
                return_value=["https://example.com/file.pdf"],
            ),
            patch(
                "webhook.processor.webhook_agent.sub_agents.download.url_download.fetch_url_bytes",
                side_effect=Exception("network error"),
            ),
        ):
            result = url_download_agent.write_record(
                "{}",
                meta_data={
                    "access": {"url": "https://example.com/file.pdf", "is_downloaded": False},
                    "identity": {"user_id": "alice"},
                },
            )
        assert result.get("status") == "error"
        assert "error_message" in result
