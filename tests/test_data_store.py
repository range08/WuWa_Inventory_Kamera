import json
import tempfile
import unittest
from pathlib import Path

from scraping.data_store import GeneratedDataStore, GameDataStoreError


VALID = {
    "items.json": {
        "item": {"id": 1, "name": "Item", "image": "item.png"}
    },
    "characters.json": {"character": 2},
    "weapons.json": {
        "weapon": {
            "id": 3,
            "name": "Weapon",
            "image": "weapon.png",
            "rarity": 5,
        }
    },
    "echoes.json": {"echo": 4},
    "achievements.json": {"Achievement": 5},
    "echoStats.json": {"attack": "atk"},
    "definedText.json": {"button": "claim"},
    "sonataName.json": ["set-one"],
}


def write_fixture(root: Path, overrides=None):
    payloads = {**VALID, **(overrides or {})}
    for filename, payload in payloads.items():
        (root / filename).write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )


class GeneratedDataStoreTests(unittest.TestCase):
    def test_reload_updates_stable_containers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            store = GeneratedDataStore()
            items_reference = store.items
            sonata_reference = store.sonata_names

            counts = store.reload(root)

            self.assertIs(store.items, items_reference)
            self.assertIs(store.sonata_names, sonata_reference)
            self.assertEqual(store.items["item"]["id"], 1)
            self.assertEqual(store.sonata_names, ["set-one"])
            self.assertEqual(counts["items.json"], 1)

    def test_invalid_mapping_fails_before_live_state_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            store = GeneratedDataStore()
            store.reload(root)
            before_items = dict(store.items)
            before_sonata = list(store.sonata_names)

            write_fixture(root, {"weapons.json": []})
            with self.assertRaisesRegex(GameDataStoreError, "JSON object"):
                store.reload(root)

            self.assertEqual(store.items, before_items)
            self.assertEqual(store.sonata_names, before_sonata)

    def test_missing_mapping_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            (root / "echoes.json").unlink()

            with self.assertRaisesRegex(GameDataStoreError, "echoes.json"):
                GeneratedDataStore().reload(root)


    def test_invalid_nested_item_record_fails_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(root)
            store = GeneratedDataStore()
            store.reload(root)
            before = dict(store.items)

            write_fixture(
                root,
                {"items.json": {"item": {"id": 1, "name": "Item"}}},
            )
            with self.assertRaisesRegex(GameDataStoreError, "image"):
                store.reload(root)

            self.assertEqual(store.items, before)

    def test_invalid_weapon_rarity_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_fixture(
                root,
                {
                    "weapons.json": {
                        "weapon": {
                            "id": 3,
                            "name": "Weapon",
                            "image": "weapon.png",
                            "rarity": 6,
                        }
                    }
                },
            )

            with self.assertRaisesRegex(GameDataStoreError, "rarity"):
                GeneratedDataStore().reload(root)


if __name__ == "__main__":
    unittest.main()
