import unittest

from updater.providers import ArikatsuDataProvider


class ArikatsuDataProviderTests(unittest.TestCase):
    def test_parses_version_metadata(self):
        provider = ArikatsuDataProvider(ref="3.6")
        metadata = provider.parse_metadata(
            "# WW_Data\n"
            "> Client region: Global</br>\n"
            "> Status: Release</br>\n"
            "> Game Version: 3.6.0</br>\n"
            "> Resource Version: 3.6.6</br>\n"
            "> Changelist: 8499915\n"
        )

        self.assertEqual(metadata.repository, "Arikatsu/WutheringWaves_Data")
        self.assertEqual(metadata.ref, "3.6")
        self.assertEqual(metadata.game_version, "3.6.0")
        self.assertEqual(metadata.resource_version, "3.6.6")
        self.assertEqual(metadata.changelist, "8499915")

    def test_required_paths_include_global_data_inputs(self):
        paths = ArikatsuDataProvider().required_paths("ko")
        self.assertIn("BinData/item/iteminfo.json", paths)
        self.assertIn("BinData/weapon/weaponconf.json", paths)
        self.assertIn("BinData/role/roleinfo.json", paths)
        self.assertIn("BinData/main_role_change/mainroleconfig.json", paths)
        self.assertIn("BinData/monster_Info/monsterinfo.json", paths)
        self.assertIn("Textmaps/ko/multi_text/MultiText.json", paths)

    def test_rejects_unsafe_path_and_language(self):
        provider = ArikatsuDataProvider()
        with self.assertRaises(ValueError):
            provider.raw_url("../secret")
        with self.assertRaises(ValueError):
            provider.required_paths("../ko")

    def test_missing_metadata_fails_closed(self):
        provider = ArikatsuDataProvider()
        with self.assertRaises(ValueError):
            provider.parse_metadata("# incomplete")


if __name__ == "__main__":
    unittest.main()
