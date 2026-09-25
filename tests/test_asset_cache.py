import json
import tempfile
import unittest
from pathlib import Path

from tools.update_assets import select_paths
from updater.asset_cache import AssetCache, AssetCacheError, PNG_SIGNATURE
from updater.asset_provider import UIAssetProvider


class FakeFetcher:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        if url not in self.payloads:
            raise AssertionError(f"Unexpected URL: {url}")
        return self.payloads[url]


class AssetProviderTests(unittest.TestCase):
    def test_maps_scanner_asset_path_to_ui_resource_repository(self):
        provider = UIAssetProvider("3.6")
        self.assertEqual(
            provider.repository_path("IconA/Activity/T_Test_UI.png"),
            "UIResources/Common/Image/IconA/Activity/T_Test_UI.png",
        )
        self.assertIn(
            "/3.6/UIResources/Common/Image/IconA/Activity/T_Test_UI.png",
            provider.raw_url("IconA/Activity/T_Test_UI.png"),
        )

    def test_rejects_unsafe_asset_paths(self):
        provider = UIAssetProvider("3.6")
        for path in ("../secret.png", "/absolute.png", r"IconA\bad.png", ""):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    provider.repository_path(path)


class AssetCacheTests(unittest.TestCase):
    def fixture(self, revision="a" * 40):
        provider = UIAssetProvider("3.6")
        asset_path = "IconA/T_Test_UI.png"
        png = PNG_SIGNATURE + b"fixture-png"
        payloads = {
            provider.revision_url(): json.dumps({"sha": revision}).encode(),
            provider.raw_url(asset_path, revision): png,
        }
        return provider, asset_path, png, payloads

    def test_sync_pins_revision_hashes_and_reuses_valid_file(self):
        provider, asset_path, png, payloads = self.fixture()
        fetcher = FakeFetcher(payloads)

        with tempfile.TemporaryDirectory() as tmp:
            cache = AssetCache(tmp, fetcher)
            first = cache.sync(provider, [asset_path])
            self.assertEqual(first["downloaded"], 1)
            self.assertEqual(first["reused"], 0)
            self.assertEqual((Path(tmp) / asset_path).read_bytes(), png)

            manifest = json.loads(
                (Path(tmp) / "asset_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["source"]["revision"], "a" * 40)
            self.assertEqual(manifest["source"]["repository"], provider.repository)
            self.assertIn(asset_path, manifest["files"])

            fetcher.calls.clear()
            second = cache.sync(provider, [asset_path])
            self.assertEqual(second["downloaded"], 0)
            self.assertEqual(second["reused"], 1)
            self.assertEqual(fetcher.calls, [provider.revision_url()])

    def test_new_revision_does_not_reuse_old_asset(self):
        provider, asset_path, old_png, old_payloads = self.fixture("a" * 40)

        with tempfile.TemporaryDirectory() as tmp:
            AssetCache(tmp, FakeFetcher(old_payloads)).sync(provider, [asset_path])

            new_revision = "b" * 40
            new_png = PNG_SIGNATURE + b"new-revision"
            new_payloads = {
                provider.revision_url(): json.dumps({"sha": new_revision}).encode(),
                provider.raw_url(asset_path, new_revision): new_png,
            }
            result = AssetCache(tmp, FakeFetcher(new_payloads)).sync(
                provider,
                [asset_path],
            )

            self.assertEqual(result["downloaded"], 1)
            self.assertEqual(result["reused"], 0)
            self.assertNotEqual(old_png, new_png)
            self.assertEqual((Path(tmp) / asset_path).read_bytes(), new_png)

    def test_rejects_non_png_payload(self):
        provider, asset_path, _, payloads = self.fixture()
        payloads[provider.raw_url(asset_path, "a" * 40)] = b"not an image"

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(AssetCacheError):
                AssetCache(tmp, FakeFetcher(payloads)).sync(provider, [asset_path])


class AssetSelectionTests(unittest.TestCase):
    def setUp(self):
        self.mapping = {
            "itema": {"id": 1, "image": "IconA/A.png"},
            "itemb": {"id": 2, "image": "IconB/B.png"},
            "itemc": {"id": 3, "image": ""},
        }

    def test_selects_only_icons_present_in_inventory(self):
        self.assertEqual(
            select_paths(self.mapping, {"2": 10, "999": 1}),
            {"IconB/B.png"},
        )

    def test_all_mode_selects_all_nonempty_icons(self):
        self.assertEqual(
            select_paths(self.mapping, None),
            {"IconA/A.png", "IconB/B.png"},
        )


if __name__ == "__main__":
    unittest.main()
