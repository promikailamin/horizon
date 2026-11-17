import tempfile
import unittest
import zipfile
from pathlib import Path

from tools import android_build as ab


class ResourceZipTests(unittest.TestCase):
    def test_a_prepared_folder_is_wrapped_in_its_own_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepared = root / "horizon-resources"
            prepared.mkdir()
            (prepared / "horizon-resources.json").write_text("{}")
            (prepared / "textures").mkdir()
            (prepared / "textures" / "a.png").write_bytes(b"png")
            output = root / "assets" / "horizon-resources.zip"
            ab.resource_zip(prepared, output)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(
                    sorted(archive.namelist()),
                    ["horizon-resources/horizon-resources.json",
                     "horizon-resources/textures/a.png"],
                )

    def test_a_folder_without_the_manifest_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(SystemExit):
                ab.resource_zip(root, root / "out.zip")


class NewestTests(unittest.TestCase):
    def test_versions_compare_as_numbers_not_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("9.0.0", "35.0.0", "27.3.13750724"):
                (root / name).mkdir()
            self.assertEqual(ab.newest(root).name, "35.0.0")


if __name__ == "__main__":
    unittest.main()
