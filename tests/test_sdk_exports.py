"""Exercise SDK symbol discovery with small, independently authored TBD files."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audit import sdk_exports


class SDKExportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.sdk = Path(self.directory.name)

    def write_stub(self, name, content):
        path = self.sdk / ('usr/lib/' + name + '.tbd')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def test_ios27_arm64e_exports_and_reexported_libraries_are_found(self):
        self.write_stub('libExample', '''--- !tapi-tbd
tbd-version: 4
targets: [ arm64e-ios, arm64e.x1-ios ]
install-name: /usr/lib/libExample.dylib
exports:
  - targets: [ arm64e-ios, arm64e.x1-ios ]
    symbols: [ _deviceFunction ]
    objc-classes: [ ExampleClass ]
  - targets: [ arm64e-maccatalyst ]
    symbols: [ _catalystOnly ]
reexported-libraries:
  - targets: [ arm64e-ios ]
    libraries: [ /usr/lib/libChild.dylib ]
''')
        self.write_stub('libChild', '''--- !tapi-tbd
tbd-version: 4
targets: [ arm64e-ios ]
install-name: /usr/lib/libChild.dylib
exports:
  - targets: [ arm64e-ios ]
    symbols: [ _childFunction ]
''')
        self.assertEqual(sdk_exports(self.sdk, '/usr/lib/libExample.dylib'), {
            '_deviceFunction', '_childFunction', '_OBJC_CLASS_$_ExampleClass',
            '_OBJC_METACLASS_$_ExampleClass',
        })

    def test_older_arm64_and_simulator_exports_remain_supported(self):
        self.write_stub('libExample', '''--- !tapi-tbd
tbd-version: 4
targets: [ arm64-ios, arm64-ios-simulator, arm64-maccatalyst ]
install-name: /usr/lib/libExample.dylib
exports:
  - targets: [ arm64-ios ]
    symbols: [ _deviceFunction ]
  - targets: [ arm64-ios-simulator ]
    symbols: [ _simulatorFunction ]
  - targets: [ arm64-maccatalyst ]
    symbols: [ _catalystOnly ]
''')
        self.assertEqual(sdk_exports(self.sdk, '/usr/lib/libExample.dylib'),
                         {'_deviceFunction', '_simulatorFunction'})


if __name__ == '__main__':
    unittest.main()
