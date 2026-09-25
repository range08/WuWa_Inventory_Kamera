import hashlib
import json
import tempfile
import unittest

from updater.providers import ArikatsuDataProvider
from updater.source_cache import SourceCache, SourceCacheError


class FakeFetcher:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        if url not in self.payloads:
            raise AssertionError(f"Unexpected URL: {url}")
        return self.payloads[url]


class SourceCacheTests(unittest.TestCase):
    def make_fixture(self):
        provider = ArikatsuDataProvider("3.6")
        revision = "a" * 40
        readme = (
            "# WW_Data\n"
            "> Client region: Global</br>\n"
            "> Status: Release</br>\n"
            "> Game Version: 3.6.0</br>\n"
            "> Resource Version: 3.6.6</br>\n"
            "> Changelist: 8499915\n"
        ).encode()

        payloads = {
            provider.revision_url(): json.dumps({"sha": revision}).encode(),
            provider.metadata_url(): readme,
        }
        for language in ("ko", "en"):
            for path in provider.required_paths(language):
                if path != "README.md":
                    payloads[provider.raw_url(path)] = f"fixture:{path}".encode()

        return provider, revision, payloads

    def test_sync_records_revision_metadata_and_hashes(self):
        provider, revision, payloads = self.make_fixture()
        fetcher = FakeFetcher(payloads)

        with tempfile.TemporaryDirectory() as tmp:
            cache = SourceCache(tmp, fetcher)
            manifest_path = cache.sync(provider, "ko")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(manifest["revision"], revision)
            self.assertEqual(manifest["source"]["game_version"], "3.6.0")
            self.assertEqual(manifest["source"]["resource_version"], "3.6.6")
            self.assertEqual(manifest["source"]["changelist"], "8499915")
            self.assertEqual(manifest["language"], "ko")

            expected = payloads[provider.raw_url("BinData/role/roleinfo.json")]
            entry = manifest["files"]["BinData/role/roleinfo.json"]
            self.assertEqual(entry["sha256"], hashlib.sha256(expected).hexdigest())
            self.assertEqual(entry["size"], len(expected))

            validated = cache.validate(manifest_path)
            self.assertEqual(validated["revision"], revision)

    def test_validation_detects_tampering(self):
        provider, _, payloads = self.make_fixture()

        with tempfile.TemporaryDirectory() as tmp:
            cache = SourceCache(tmp, FakeFetcher(payloads))
            manifest_path = cache.sync(provider, "ko")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            target = manifest_path.parent / next(iter(manifest["files"]))
            target.write_bytes(b"tampered")

            with self.assertRaises(SourceCacheError):
                cache.validate(manifest_path)

    def test_invalid_revision_fails_closed(self):
        provider, _, payloads = self.make_fixture()
        payloads[provider.revision_url()] = json.dumps({"sha": "not-a-sha"}).encode()

        with tempfile.TemporaryDirectory() as tmp:
            cache = SourceCache(tmp, FakeFetcher(payloads))
            with self.assertRaises(SourceCacheError):
                cache.sync(provider, "ko", allow_cached_fallback=False)

    def test_sync_reuses_valid_cache_for_same_revision(self):
        provider, _, payloads = self.make_fixture()
        fetcher = FakeFetcher(payloads)

        with tempfile.TemporaryDirectory() as tmp:
            cache = SourceCache(tmp, fetcher)
            manifest_path = cache.sync(provider, "ko")

            fetcher.calls.clear()
            reused_path = cache.sync(provider, "ko")

            self.assertEqual(reused_path, manifest_path)
            self.assertEqual(fetcher.calls, [provider.revision_url()])

    def test_sync_falls_back_to_valid_cache_when_revision_lookup_fails(self):
        provider, _, payloads = self.make_fixture()

        with tempfile.TemporaryDirectory() as tmp:
            cache = SourceCache(tmp, FakeFetcher(payloads))
            manifest_path = cache.sync(provider, "ko")

            def failing_fetcher(url):
                raise SourceCacheError("offline")

            offline_cache = SourceCache(tmp, failing_fetcher)
            reused_path = offline_cache.sync(provider, "ko")

            self.assertEqual(reused_path, manifest_path)
            self.assertEqual(
                offline_cache.latest_valid(provider, "ko"),
                manifest_path,
            )


    def test_sync_falls_back_when_metadata_download_fails(self):
        provider, _, payloads = self.make_fixture()

        with tempfile.TemporaryDirectory() as tmp:
            cache = SourceCache(tmp, FakeFetcher(payloads))
            manifest_path = cache.sync(provider, "ko")

            def metadata_failure(url):
                if url == provider.revision_url():
                    return payloads[url]
                raise SourceCacheError("metadata unavailable")

            fallback_cache = SourceCache(tmp, metadata_failure)
            self.assertEqual(fallback_cache.sync(provider, "ko"), manifest_path)

    def test_sync_falls_back_when_source_file_download_fails(self):
        provider, _, payloads = self.make_fixture()

        with tempfile.TemporaryDirectory() as tmp:
            cache = SourceCache(tmp, FakeFetcher(payloads))
            manifest_path = cache.sync(provider, "ko")

            def file_failure(url):
                if url in (provider.revision_url(), provider.metadata_url()):
                    return payloads[url]
                raise SourceCacheError("source file unavailable")

            fallback_cache = SourceCache(tmp, file_failure)
            self.assertEqual(fallback_cache.sync(provider, "ko"), manifest_path)

    def test_remote_failure_stays_fatal_when_fallback_disabled(self):
        provider, _, payloads = self.make_fixture()

        with tempfile.TemporaryDirectory() as tmp:
            cache = SourceCache(tmp, FakeFetcher(payloads))
            cache.sync(provider, "ko")

            def metadata_failure(url):
                if url == provider.revision_url():
                    return payloads[url]
                raise SourceCacheError("metadata unavailable")

            strict_cache = SourceCache(tmp, metadata_failure)
            with self.assertRaises(SourceCacheError):
                strict_cache.sync(
                    provider,
                    "ko",
                    allow_cached_fallback=False,
                )

    def test_latest_valid_rejects_other_language(self):
        provider, _, payloads = self.make_fixture()

        with tempfile.TemporaryDirectory() as tmp:
            cache = SourceCache(tmp, FakeFetcher(payloads))
            cache.sync(provider, "ko")

            with self.assertRaises(SourceCacheError):
                cache.latest_valid(provider, "en")

    def test_same_revision_keeps_languages_in_separate_caches(self):
        provider, _, payloads = self.make_fixture()

        with tempfile.TemporaryDirectory() as tmp:
            cache = SourceCache(tmp, FakeFetcher(payloads))
            ko_manifest = cache.sync(provider, "ko")
            en_manifest = cache.sync(provider, "en")

            self.assertNotEqual(ko_manifest, en_manifest)
            self.assertEqual(ko_manifest.parent.name, "ko")
            self.assertEqual(en_manifest.parent.name, "en")
            self.assertEqual(cache.latest_valid(provider, "ko"), ko_manifest)
            self.assertEqual(cache.latest_valid(provider, "en"), en_manifest)

    def test_validation_rejects_unsafe_manifest_path(self):
        provider, _, payloads = self.make_fixture()

        with tempfile.TemporaryDirectory() as tmp:
            cache = SourceCache(tmp, FakeFetcher(payloads))
            manifest_path = cache.sync(provider, "ko")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            payload = b"outside"
            outside = manifest_path.parent.parent / "outside.json"
            outside.write_bytes(payload)
            manifest["files"] = {
                "../outside.json": {
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size": len(payload),
                }
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(SourceCacheError, "unsafe file path"):
                cache.validate(manifest_path)

    def test_latest_valid_rejects_cache_missing_required_inputs(self):
        provider, _, payloads = self.make_fixture()

        with tempfile.TemporaryDirectory() as tmp:
            cache = SourceCache(tmp, FakeFetcher(payloads))
            manifest_path = cache.sync(provider, "ko")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            required = provider.required_paths("ko")
            missing = next(
                path
                for path in required
                if path.startswith("Textmaps/en/")
            )
            manifest["files"].pop(missing)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            self.assertEqual(cache.validate(manifest_path)["language"], "ko")
            with self.assertRaises(SourceCacheError):
                cache.latest_valid(provider, "ko")


if __name__ == "__main__":
    unittest.main()
