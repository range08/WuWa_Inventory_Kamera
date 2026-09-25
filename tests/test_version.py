import re
import unittest

from version import __version__


class VersionTests(unittest.TestCase):
    def test_version_is_pep440_compatible_simple_release(self):
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+(?:[ab]|rc|\.dev)?\d*$")


if __name__ == "__main__":
    unittest.main()
