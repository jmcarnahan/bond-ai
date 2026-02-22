"""Tests for file/drive operations (sync and async)."""

import httpx
import pytest
import respx

from ms_graph.graph_client import GRAPH_BASE_URL, AsyncGraphClient, GraphClient
from ms_graph import files
from .conftest import (
    SAMPLE_DRIVE_CHILDREN_RESPONSE,
    SAMPLE_DRIVE_ITEM_BINARY,
    SAMPLE_DRIVE_ITEM_FILE,
    SAMPLE_DRIVE_ITEM_FOLDER,
    SAMPLE_DRIVE_ITEM_LARGE_TEXT,
    SAMPLE_SEARCH_RESPONSE,
    SAMPLE_SEARCH_RESPONSE_EMPTY,
    SAMPLE_SITE,
    SAMPLE_SITES_RESPONSE,
)


class TestFilesSync:
    """Synchronous file operation tests."""

    @respx.mock
    def test_list_drive_children_root(self):
        respx.get(f"{GRAPH_BASE_URL}/me/drive/root/children").mock(
            return_value=httpx.Response(200, json=SAMPLE_DRIVE_CHILDREN_RESPONSE)
        )
        with GraphClient("tok") as client:
            items = files.list_drive_children(client)

        assert len(items) == 3
        assert items[0]["name"] == "Documents"
        assert items[1]["name"] == "report.csv"

    @respx.mock
    def test_list_drive_children_subfolder(self):
        respx.get(f"{GRAPH_BASE_URL}/me/drive/root:/Documents:/children").mock(
            return_value=httpx.Response(200, json={"value": [SAMPLE_DRIVE_ITEM_FILE]})
        )
        with GraphClient("tok") as client:
            items = files.list_drive_children(client, folder_path="Documents")

        assert len(items) == 1
        assert items[0]["name"] == "report.csv"

    @respx.mock
    def test_list_drive_children_sharepoint(self):
        respx.get(f"{GRAPH_BASE_URL}/sites/site-id-001/drive/root/children").mock(
            return_value=httpx.Response(200, json=SAMPLE_DRIVE_CHILDREN_RESPONSE)
        )
        with GraphClient("tok") as client:
            items = files.list_drive_children(client, site_id="site-id-001")

        assert len(items) == 3

    @respx.mock
    def test_get_drive_item(self):
        respx.get(f"{GRAPH_BASE_URL}/me/drive/items/file-id-001").mock(
            return_value=httpx.Response(200, json=SAMPLE_DRIVE_ITEM_FILE)
        )
        with GraphClient("tok") as client:
            item = files.get_drive_item(client, "file-id-001")

        assert item["name"] == "report.csv"
        assert item["size"] == 1024

    @respx.mock
    def test_get_drive_item_content_text(self):
        csv_content = b"header1,header2\nvalue1,value2\n"
        respx.get(f"{GRAPH_BASE_URL}/me/drive/items/file-id-001").mock(
            return_value=httpx.Response(200, json=SAMPLE_DRIVE_ITEM_FILE)
        )
        respx.get(f"{GRAPH_BASE_URL}/me/drive/items/file-id-001/content").mock(
            return_value=httpx.Response(200, content=csv_content)
        )
        with GraphClient("tok") as client:
            item, content = files.get_drive_item_content(client, "file-id-001")

        assert item["name"] == "report.csv"
        assert content == "header1,header2\nvalue1,value2\n"

    @respx.mock
    def test_get_drive_item_content_binary(self):
        respx.get(f"{GRAPH_BASE_URL}/me/drive/items/file-id-002").mock(
            return_value=httpx.Response(200, json=SAMPLE_DRIVE_ITEM_BINARY)
        )
        with GraphClient("tok") as client:
            item, content = files.get_drive_item_content(client, "file-id-002")

        assert item["name"] == "presentation.pptx"
        assert content is None

    @respx.mock
    def test_get_drive_item_content_too_large(self):
        respx.get(f"{GRAPH_BASE_URL}/me/drive/items/file-id-003").mock(
            return_value=httpx.Response(200, json=SAMPLE_DRIVE_ITEM_LARGE_TEXT)
        )
        with GraphClient("tok") as client:
            item, content = files.get_drive_item_content(client, "file-id-003")

        assert item["name"] == "huge-log.txt"
        assert content is None  # Too large, skipped

    @respx.mock
    def test_search_drive(self):
        respx.get(f"{GRAPH_BASE_URL}/me/drive/root/search(q='report')").mock(
            return_value=httpx.Response(200, json={"value": [SAMPLE_DRIVE_ITEM_FILE]})
        )
        with GraphClient("tok") as client:
            results = files.search_drive(client, "report")

        assert len(results) == 1
        assert results[0]["name"] == "report.csv"

    @respx.mock
    def test_search_files_unified(self):
        respx.post(f"{GRAPH_BASE_URL}/search/query").mock(
            return_value=httpx.Response(200, json=SAMPLE_SEARCH_RESPONSE)
        )
        with GraphClient("tok") as client:
            results = files.search_files_unified(client, "budget")

        assert len(results) == 2
        assert results[0]["name"] == "Q4-budget.xlsx"
        assert results[0]["_searchSummary"] == "Q4 <c0>budget</c0> projections for 2025"
        assert results[1]["name"] == "budget-notes.md"

    @respx.mock
    def test_search_files_unified_empty(self):
        respx.post(f"{GRAPH_BASE_URL}/search/query").mock(
            return_value=httpx.Response(200, json=SAMPLE_SEARCH_RESPONSE_EMPTY)
        )
        with GraphClient("tok") as client:
            results = files.search_files_unified(client, "nonexistent")

        assert results == []

    @respx.mock
    def test_list_sites(self):
        respx.get(f"{GRAPH_BASE_URL}/sites").mock(
            return_value=httpx.Response(200, json=SAMPLE_SITES_RESPONSE)
        )
        with GraphClient("tok") as client:
            sites = files.list_sites(client, query="engineering")

        assert len(sites) == 2
        assert sites[0]["displayName"] == "Engineering Hub"

    @respx.mock
    def test_search_files_unified_consumer_fallback(self):
        """Consumer accounts get 400 from /search/query — should fall back to per-drive search."""
        respx.post(f"{GRAPH_BASE_URL}/search/query").mock(
            return_value=httpx.Response(
                400,
                json={"error": {"code": "BadRequest", "message": "This API is not supported for MSA accounts"}},
            )
        )
        respx.get(f"{GRAPH_BASE_URL}/me/drive/root/search(q='report')").mock(
            return_value=httpx.Response(200, json={"value": [SAMPLE_DRIVE_ITEM_FILE]})
        )
        with GraphClient("tok") as client:
            results = files.search_files_unified(client, "report")

        assert len(results) == 1
        assert results[0]["name"] == "report.csv"

    @respx.mock
    def test_list_sites_followed(self):
        respx.get(f"{GRAPH_BASE_URL}/me/followedSites").mock(
            return_value=httpx.Response(200, json={"value": [SAMPLE_SITE]})
        )
        with GraphClient("tok") as client:
            sites = files.list_sites(client)

        assert len(sites) == 1
        assert sites[0]["displayName"] == "Engineering Hub"


class TestFilesAsync:
    """Async file operation tests."""

    @respx.mock
    async def test_alist_drive_children_root(self):
        respx.get(f"{GRAPH_BASE_URL}/me/drive/root/children").mock(
            return_value=httpx.Response(200, json=SAMPLE_DRIVE_CHILDREN_RESPONSE)
        )
        async with AsyncGraphClient("tok") as client:
            items = await files.alist_drive_children(client)

        assert len(items) == 3

    @respx.mock
    async def test_alist_drive_children_subfolder(self):
        respx.get(f"{GRAPH_BASE_URL}/me/drive/root:/Projects:/children").mock(
            return_value=httpx.Response(200, json={"value": [SAMPLE_DRIVE_ITEM_FILE]})
        )
        async with AsyncGraphClient("tok") as client:
            items = await files.alist_drive_children(client, folder_path="Projects")

        assert len(items) == 1

    @respx.mock
    async def test_alist_drive_children_sharepoint(self):
        respx.get(f"{GRAPH_BASE_URL}/sites/site-id-001/drive/root/children").mock(
            return_value=httpx.Response(200, json=SAMPLE_DRIVE_CHILDREN_RESPONSE)
        )
        async with AsyncGraphClient("tok") as client:
            items = await files.alist_drive_children(client, site_id="site-id-001")

        assert len(items) == 3

    @respx.mock
    async def test_aget_drive_item(self):
        respx.get(f"{GRAPH_BASE_URL}/me/drive/items/file-id-001").mock(
            return_value=httpx.Response(200, json=SAMPLE_DRIVE_ITEM_FILE)
        )
        async with AsyncGraphClient("tok") as client:
            item = await files.aget_drive_item(client, "file-id-001")

        assert item["name"] == "report.csv"

    @respx.mock
    async def test_aget_drive_item_content_text(self):
        csv_content = b"col1,col2\na,b\n"
        respx.get(f"{GRAPH_BASE_URL}/me/drive/items/file-id-001").mock(
            return_value=httpx.Response(200, json=SAMPLE_DRIVE_ITEM_FILE)
        )
        respx.get(f"{GRAPH_BASE_URL}/me/drive/items/file-id-001/content").mock(
            return_value=httpx.Response(200, content=csv_content)
        )
        async with AsyncGraphClient("tok") as client:
            item, content = await files.aget_drive_item_content(client, "file-id-001")

        assert content == "col1,col2\na,b\n"

    @respx.mock
    async def test_aget_drive_item_content_binary(self):
        respx.get(f"{GRAPH_BASE_URL}/me/drive/items/file-id-002").mock(
            return_value=httpx.Response(200, json=SAMPLE_DRIVE_ITEM_BINARY)
        )
        async with AsyncGraphClient("tok") as client:
            item, content = await files.aget_drive_item_content(client, "file-id-002")

        assert content is None

    @respx.mock
    async def test_aget_drive_item_content_too_large(self):
        respx.get(f"{GRAPH_BASE_URL}/me/drive/items/file-id-003").mock(
            return_value=httpx.Response(200, json=SAMPLE_DRIVE_ITEM_LARGE_TEXT)
        )
        async with AsyncGraphClient("tok") as client:
            item, content = await files.aget_drive_item_content(client, "file-id-003")

        assert content is None

    @respx.mock
    async def test_asearch_drive(self):
        respx.get(f"{GRAPH_BASE_URL}/me/drive/root/search(q='report')").mock(
            return_value=httpx.Response(200, json={"value": [SAMPLE_DRIVE_ITEM_FILE]})
        )
        async with AsyncGraphClient("tok") as client:
            results = await files.asearch_drive(client, "report")

        assert len(results) == 1

    @respx.mock
    async def test_asearch_files_unified(self):
        respx.post(f"{GRAPH_BASE_URL}/search/query").mock(
            return_value=httpx.Response(200, json=SAMPLE_SEARCH_RESPONSE)
        )
        async with AsyncGraphClient("tok") as client:
            results = await files.asearch_files_unified(client, "budget")

        assert len(results) == 2
        assert "_searchSummary" in results[0]

    @respx.mock
    async def test_asearch_files_unified_empty(self):
        respx.post(f"{GRAPH_BASE_URL}/search/query").mock(
            return_value=httpx.Response(200, json=SAMPLE_SEARCH_RESPONSE_EMPTY)
        )
        async with AsyncGraphClient("tok") as client:
            results = await files.asearch_files_unified(client, "nonexistent")

        assert results == []

    @respx.mock
    async def test_alist_sites(self):
        respx.get(f"{GRAPH_BASE_URL}/sites").mock(
            return_value=httpx.Response(200, json=SAMPLE_SITES_RESPONSE)
        )
        async with AsyncGraphClient("tok") as client:
            sites = await files.alist_sites(client, query="engineering")

        assert len(sites) == 2

    @respx.mock
    async def test_asearch_files_unified_consumer_fallback(self):
        """Consumer accounts get 400 from /search/query — should fall back to per-drive search."""
        respx.post(f"{GRAPH_BASE_URL}/search/query").mock(
            return_value=httpx.Response(
                400,
                json={"error": {"code": "BadRequest", "message": "This API is not supported for MSA accounts"}},
            )
        )
        respx.get(f"{GRAPH_BASE_URL}/me/drive/root/search(q='report')").mock(
            return_value=httpx.Response(200, json={"value": [SAMPLE_DRIVE_ITEM_FILE]})
        )
        async with AsyncGraphClient("tok") as client:
            results = await files.asearch_files_unified(client, "report")

        assert len(results) == 1
        assert results[0]["name"] == "report.csv"

    @respx.mock
    async def test_alist_sites_followed(self):
        respx.get(f"{GRAPH_BASE_URL}/me/followedSites").mock(
            return_value=httpx.Response(200, json={"value": [SAMPLE_SITE]})
        )
        async with AsyncGraphClient("tok") as client:
            sites = await files.alist_sites(client)

        assert len(sites) == 1
