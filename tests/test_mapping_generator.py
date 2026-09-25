import json
import tempfile
import unittest
from pathlib import Path

from updater.mapping_generator import (
    MappingGenerationError,
    generate_achievements,
    generate_characters,
    generate_echoes,
    generate_items,
    generate_weapons,
    generate_from_cache,
    generated_mappings_current,
    image_filename,
    load_textmap,
    normalize_name,
)


class MappingGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.textmap = {
            "RoleInfo_1205_Name": "Changli",
            "WeaponConf_21020064_WeaponName": "Blazing Brilliance",
            "ItemInfo_43010001_Name": "Basic Resonance Potion",
            "MonsterInfo_340000070_Name": "Dreamless",
            "Achievement_1001_Name": "A Moment for the Ages",
        }

    def test_generates_legacy_compatible_core_mappings(self):
        characters = generate_characters(
            [{"Id": 1205, "Name": "RoleInfo_1205_Name"}],
            self.textmap,
        )
        weapons = generate_weapons(
            [{
                "ItemId": 21020064,
                "ModelId": 21020064,
                "WeaponName": "WeaponConf_21020064_WeaponName",
                "QualityId": 5,
                "Icon": "/Game/Aki/UI/UIResources/Common/Image/IconWeapon/T_IconWeapon21020064_UI.T_IconWeapon21020064_UI",
            }],
            self.textmap,
        )
        items = generate_items(
            [{
                "Id": 43010001,
                "Name": "ItemInfo_43010001_Name",
                "Icon": "/Game/Aki/UI/UIResources/Common/Image/IconA/T_Item_UI.T_Item_UI",
            }],
            self.textmap,
        )
        echoes = generate_echoes(
            [{"Id": 340000070, "Name": "MonsterInfo_340000070_Name"}],
            self.textmap,
        )
        achievements = generate_achievements(
            [{"Id": 1001, "Name": "Achievement_1001_Name"}],
            self.textmap,
        )

        self.assertEqual(characters, {"changli": 1205})
        self.assertEqual(weapons["blazingbrilliance"]["id"], 21020064)
        self.assertEqual(weapons["blazingbrilliance"]["rarity"], 5)
        self.assertEqual(
            weapons["blazingbrilliance"]["image"],
            "IconWeapon/T_IconWeapon21020064_UI.png",
        )
        self.assertEqual(items["basicresonancepotion"]["id"], 43010001)
        self.assertEqual(
            items["basicresonancepotion"]["image"],
            "IconA/T_Item_UI.png",
        )
        self.assertEqual(echoes, {"dreamless": 340000070})
        self.assertEqual(achievements, {"A Moment for the Ages": 1001})

    def test_image_filename_preserves_nested_ui_resource_path(self):
        self.assertEqual(
            image_filename(
                "/Game/Aki/UI/UIResources/Common/Image/"
                "IconA/Activity/Activity31/T_Test_UI.T_Test_UI"
            ),
            "IconA/Activity/Activity31/T_Test_UI.png",
        )
        self.assertEqual(
            image_filename("/Other/Path/T_Fallback.T_Fallback"),
            "T_Fallback.png",
        )
        self.assertEqual(image_filename(""), "")

    def test_textmap_accepts_current_id_content_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "MultiText.json"
            path.write_text(
                json.dumps([
                    {"Id": "RoleInfo_1205_Name", "Content": "Changli"},
                    {"Id": "ItemInfo_1_Name", "Content": "Item"},
                ]),
                encoding="utf-8",
            )
            self.assertEqual(
                load_textmap(path),
                {"RoleInfo_1205_Name": "Changli", "ItemInfo_1_Name": "Item"},
            )

    def test_duplicate_normalized_names_fail_closed(self):
        with self.assertRaises(MappingGenerationError):
            generate_characters(
                [
                    {"Id": 1205, "Name": "A", "ParentId": 0, "RoleType": 1},
                    {"Id": 1206, "Name": "B", "ParentId": 0, "RoleType": 1},
                ],
                {"A": "Same Name", "B": "SameName"},
            )

    def test_ambiguous_non_character_names_are_excluded(self):
        items = generate_items(
            [
                {"Id": 1, "Name": "A", "Icon": ""},
                {"Id": 2, "Name": "B", "Icon": ""},
                {"Id": 3, "Name": "C", "Icon": ""},
            ],
            {
                "A": "Duplicate",
                "B": "Duplicate",
                "C": "Unique",
            },
        )
        echoes = generate_echoes(
            [
                {"Id": 340000001, "Name": "EA"},
                {"Id": 340000002, "Name": "EB"},
                {"Id": 340000003, "Name": "EC"},
            ],
            {
                "EA": "Same Echo",
                "EB": "Same Echo",
                "EC": "Unique Echo",
            },
        )
        achievements = generate_achievements(
            [
                {"Id": 1001, "Name": "AA"},
                {"Id": 1002, "Name": "AB"},
                {"Id": 1003, "Name": "AC"},
            ],
            {
                "AA": "Same Achievement",
                "AB": "Same Achievement",
                "AC": "Unique Achievement",
            },
        )

        self.assertNotIn("duplicate", items)
        self.assertEqual(items["unique"]["id"], 3)
        self.assertNotIn("sameecho", echoes)
        self.assertEqual(echoes["uniqueecho"], 340000003)
        self.assertNotIn("Same Achievement", achievements)
        self.assertEqual(achievements["Unique Achievement"], 1003)

    def test_character_mapping_excludes_derived_and_main_role_variants(self):
        characters = generate_characters(
            [
                {"Id": 1205, "Name": "Changli", "ParentId": 0, "RoleType": 1},
                {"Id": 2005, "Name": "ChangliTrial", "ParentId": 1205, "RoleType": 5},
                {"Id": 1501, "Name": "RoverMale", "ParentId": 0, "RoleType": 1},
                {"Id": 1502, "Name": "RoverFemale", "ParentId": 0, "RoleType": 1},
            ],
            {
                "Changli": "Changli",
                "ChangliTrial": "Changli",
                "RoverMale": "Rover: Havoc",
                "RoverFemale": "Rover: Havoc",
            },
            excluded_role_ids={1501, 1502},
        )

        self.assertEqual(characters, {"changli": 1205})

    def test_generated_manifest_tracks_source_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_dir = root / "source"
            output_dir = root / "output"

            (cache_dir / "Textmaps/en/multi_text").mkdir(parents=True)
            (cache_dir / "BinData/role").mkdir(parents=True)
            (cache_dir / "BinData/main_role_change").mkdir(parents=True)
            (cache_dir / "BinData/weapon").mkdir(parents=True)
            (cache_dir / "BinData/item").mkdir(parents=True)
            (cache_dir / "BinData/monster_Info").mkdir(parents=True)
            (cache_dir / "BinData/achievement").mkdir(parents=True)

            source_manifest = {
                "schema_version": 1,
                "source": {
                    "repository": "Arikatsu/WutheringWaves_Data",
                    "ref": "3.6",
                    "game_version": "3.6.0",
                    "resource_version": "3.6.6",
                    "changelist": "8499915",
                },
                "revision": "a" * 40,
                "language": "en",
                "files": {"fixture": {"sha256": "unused", "size": 0}},
            }
            (cache_dir / "manifest.json").write_text(
                json.dumps(source_manifest),
                encoding="utf-8",
            )

            textmap = dict(self.textmap)
            textmap.update({
                "PropertyIndex_10003_Name": "HP",
                "PhantomFetter_1_Name": "Freezing Frost",
                "PrefabTextItem_1547656443_Text": "Terminal",
                "PrefabTextItem_128820487_Text": "Claim",
                "PrefabTextItem_3963945691_Text": "Activated",
            })
            (cache_dir / "Textmaps/en/multi_text/MultiText.json").write_text(
                json.dumps(textmap),
                encoding="utf-8",
            )
            (cache_dir / "BinData/role/roleinfo.json").write_text(
                json.dumps([{
                    "Id": 1205,
                    "Name": "RoleInfo_1205_Name",
                    "ParentId": 0,
                    "RoleType": 1,
                }]),
                encoding="utf-8",
            )
            (cache_dir / "BinData/main_role_change/mainroleconfig.json").write_text(
                "[]",
                encoding="utf-8",
            )
            (cache_dir / "BinData/weapon/weaponconf.json").write_text(
                json.dumps([{
                    "ItemId": 21020064,
                    "ModelId": 21020064,
                    "WeaponName": "WeaponConf_21020064_WeaponName",
                    "QualityId": 5,
                    "Icon": "",
                }]),
                encoding="utf-8",
            )
            (cache_dir / "BinData/item/iteminfo.json").write_text(
                json.dumps([{
                    "Id": 43010001,
                    "Name": "ItemInfo_43010001_Name",
                    "Icon": "",
                }]),
                encoding="utf-8",
            )
            (cache_dir / "BinData/monster_Info/monsterinfo.json").write_text(
                json.dumps([{
                    "Id": 340000070,
                    "Name": "MonsterInfo_340000070_Name",
                }]),
                encoding="utf-8",
            )
            (cache_dir / "BinData/achievement/achievement.json").write_text(
                json.dumps([{
                    "Id": 1001,
                    "Name": "Achievement_1001_Name",
                }]),
                encoding="utf-8",
            )

            counts = generate_from_cache(cache_dir, output_dir)
            self.assertEqual(
                generated_mappings_current(cache_dir, output_dir),
                counts,
            )

            characters = output_dir / "characters.json"
            characters.write_text("{}", encoding="utf-8")
            self.assertIsNone(
                generated_mappings_current(cache_dir, output_dir)
            )

    def test_malformed_source_records_fail_closed(self):
        with self.assertRaisesRegex(MappingGenerationError, "ItemInfo"):
            generate_items(
                [{"Name": "Broken item"}],
                {"Broken item": "Broken item"},
            )

        with self.assertRaisesRegex(MappingGenerationError, "WeaponConf"):
            generate_weapons(
                [{"WeaponName": "Broken weapon", "QualityId": 5}],
                {"Broken weapon": "Broken weapon"},
            )

        with self.assertRaisesRegex(MappingGenerationError, "MonsterInfo"):
            generate_echoes(
                [None],
                {},
            )

    def test_generate_from_cache_rejects_empty_required_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_dir = root / "source"
            output_dir = root / "output"

            (cache_dir / "Textmaps/en/multi_text").mkdir(parents=True)
            (cache_dir / "BinData/role").mkdir(parents=True)
            (cache_dir / "BinData/main_role_change").mkdir(parents=True)
            (cache_dir / "BinData/weapon").mkdir(parents=True)
            (cache_dir / "BinData/item").mkdir(parents=True)
            (cache_dir / "BinData/monster_Info").mkdir(parents=True)
            (cache_dir / "BinData/achievement").mkdir(parents=True)

            (cache_dir / "manifest.json").write_text(
                json.dumps({
                    "schema_version": 1,
                    "source": {
                        "repository": "Arikatsu/WutheringWaves_Data",
                        "ref": "3.6",
                        "game_version": "3.6.0",
                        "resource_version": "3.6.6",
                        "changelist": "8499915",
                    },
                    "revision": "a" * 40,
                    "language": "en",
                    "files": {"fixture": {"sha256": "unused", "size": 0}},
                }),
                encoding="utf-8",
            )
            (cache_dir / "Textmaps/en/multi_text/MultiText.json").write_text(
                "{}",
                encoding="utf-8",
            )
            (cache_dir / "BinData/role/roleinfo.json").write_text(
                json.dumps([{"Id": 1205, "Name": "RoleInfo_1205_Name"}]),
                encoding="utf-8",
            )
            (cache_dir / "BinData/main_role_change/mainroleconfig.json").write_text(
                "[]",
                encoding="utf-8",
            )
            (cache_dir / "BinData/weapon/weaponconf.json").write_text(
                json.dumps([{
                    "ItemId": 21020064,
                    "ModelId": 21020064,
                    "WeaponName": "WeaponConf_21020064_WeaponName",
                    "QualityId": 5,
                    "Icon": "",
                }]),
                encoding="utf-8",
            )
            (cache_dir / "BinData/item/iteminfo.json").write_text(
                json.dumps([{
                    "Id": 43010001,
                    "Name": "ItemInfo_43010001_Name",
                    "Icon": "",
                }]),
                encoding="utf-8",
            )
            (cache_dir / "BinData/monster_Info/monsterinfo.json").write_text(
                json.dumps([{"Id": 340000070, "Name": "MonsterInfo_340000070_Name"}]),
                encoding="utf-8",
            )
            (cache_dir / "BinData/achievement/achievement.json").write_text(
                json.dumps([{"Id": 1001, "Name": "Achievement_1001_Name"}]),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                MappingGenerationError,
                "Generated mapping is empty",
            ):
                generate_from_cache(cache_dir, output_dir)

    def test_normalization_matches_existing_scanner_convention(self):
        self.assertEqual(normalize_name("Blazing Brilliance"), "blazingbrilliance")


if __name__ == "__main__":
    unittest.main()
