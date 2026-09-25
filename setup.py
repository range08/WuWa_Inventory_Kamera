import cx_Freeze

from version import __version__

executables = [
    cx_Freeze.Executable(
        "main.py",
        base="Win32GUI",
        target_name="WuWa Inventory Kamera",
        icon="assets/icon.ico",
        uac_admin=True
    )
]

cx_Freeze.setup(
    name="WuWa Inventory Kamera",
    version=__version__,
    options={
        "build_exe": {
            "packages": ["rapidocr", "onnxruntime"],
            "excludes": [
                "tkinter", "unittest", "email", "html",
                "xml", "distutils", "setuptools", "pip", "wheel"
            ],
            "include_files": [
                ("assets", "assets")
            ],
            "optimize": 2,
            "build_exe": f"dist/v{__version__}",
            "silent_level": 0,
            "include_msvcr": True,
        }
    },
    executables=executables
)