import unittest

from rsdeck.config import default_config, normalize_config
from rsdeck.runner import _virtual_key


class ConfigurationTests(unittest.TestCase):
    def test_default_profiles_have_sixteen_actions(self):
        config = default_config()
        self.assertEqual([p["name"] for p in config["profiles"]], [
            "Default", "Adobe Premiere Pro", "Adobe Photoshop", "OBS Studio"
        ])
        for profile in config["profiles"]:
            self.assertEqual(len(profile["actions"]), 16)

    def test_normalize_pads_short_action_lists(self):
        config = normalize_config({
            "profiles": [{"id": "default", "name": "Default", "actions": [
                {"type": "hotkey", "value": "CTRL+S"}
            ]}]
        })
        actions = config["profiles"][0]["actions"]
        self.assertEqual(len(actions), 16)
        self.assertEqual(actions[0], {"type": "hotkey", "value": "CTRL+S"})
        self.assertEqual(actions[1], {"type": "none", "value": ""})

    def test_unknown_action_type_is_disabled(self):
        config = normalize_config({
            "profiles": [{"id": "default", "name": "Default", "actions": [
                {"type": "run-anything", "value": "x"}
            ]}]
        })
        self.assertEqual(config["profiles"][0]["actions"][0], {"type": "none", "value": "x"})


class HotkeyTokenTests(unittest.TestCase):
    def test_requested_hotkey_tokens_are_supported(self):
        for token in ("CTRL", "SHIFT", "ALT", "S", "F1", "F5"):
            self.assertIsInstance(_virtual_key(token), int)

    def test_unknown_key_is_rejected(self):
        with self.assertRaises(ValueError):
            _virtual_key("NO_SUCH_KEY")


if __name__ == "__main__":
    unittest.main()
