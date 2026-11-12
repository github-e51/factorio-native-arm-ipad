"""Compare a ported engine with its original using isolated saves and mod lists."""

import argparse
import json
import logging
import plistlib
import shutil
import subprocess
from pathlib import Path

from config import DEFAULT_APP, DEFAULT_BUNDLE_ID, ROOT, source_profile
from source_profiles import SourceProfile
from verify import benchmark_checksum, require

logger = logging.getLogger(__name__)


def prepare_probe(root: Path, data: Path, profile: SourceProfile, mode: str) -> Path:
    """Write a private configuration without reading or changing normal saves."""
    root.mkdir(parents=True, exist_ok=True)
    mods = root / "mods"
    mods.mkdir(exist_ok=True)
    entries = [
        {"name": name, "enabled": name == "base" or mode == "space-age"}
        for name, _ in profile.mods
        if name != "core"
    ]
    (mods / "mod-list.json").write_text(json.dumps({"mods": entries}, indent=2) + "\n")
    config = root / "config.ini"
    config.write_text(
        f"[path]\nread-data={data}\nwrite-data={root}\n[general]\ncheck-updates=false\n"
        "[other]\nenable-crash-log-uploading=false\n"
    )
    (root / "map-gen-settings.json").write_text(
        '{"width":64,"height":64,"seed":12345}\n'
    )
    if mode == "space-age":
        scenario = root / "scenarios/port-validation"
        scenario.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(
            ROOT / "tests/scenarios/space-age/control.lua", scenario / "control.lua"
        )
    return config


def run_logged(
    prefix: list[str], arguments: list[str], config: Path, log_path: Path
) -> str:
    """Run one bounded CLI probe and reject crashes even if simctl reports success."""
    logger.info("Running %s", log_path.name)
    command = [
        *prefix,
        *arguments,
        "--config",
        str(config),
        "--mod-directory",
        str(config.parent / "mods"),
        "--disable-audio",
        "--nogamepad",
    ]
    with log_path.open("w") as log:
        result = subprocess.run(
            command, stdout=log, stderr=subprocess.STDOUT, timeout=180, check=False
        )
    output = log_path.read_text()
    require(result.returncode == 0, f"Probe failed ({result.returncode}): {log_path}")
    require(
        "Factorio crashed." not in output
        and "FACTORIO_PROBE_UNIMPLEMENTED:" not in output,
        f"Probe crashed: {log_path}",
    )
    require("Goodbye" in output, f"Probe did not finish: {log_path}")
    return output


def main() -> None:
    """Create native evidence and optionally compare the installed simulator port."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, default=DEFAULT_APP)
    parser.add_argument("--mode", choices=["base", "space-age"], default="space-age")
    parser.add_argument(
        "--simulator", help="Run against this already booted simulator as well"
    )
    parser.add_argument("--bundle-id", default=DEFAULT_BUNDLE_ID)
    args = parser.parse_args()
    profile = source_profile(args.app)
    if args.mode == "space-age" and profile.edition != "space-age":
        parser.error(
            "Space Age probes require the analyzed expansion executable and assets"
        )
    (ROOT / "reports").mkdir(exist_ok=True)
    label = f"{profile.key}-{args.mode}"
    native_root = ROOT / "build/simulation" / label / "native"
    native_config = prepare_probe(
        native_root, args.app / "Contents/data", profile, args.mode
    )
    prefix = [str(args.app / "Contents/MacOS/factorio")]
    log_prefix = ROOT / f"reports/simulation-{label}"
    save = native_root / "probe-map.zip"
    run_logged(
        prefix,
        [
            "--create",
            str(save),
            "--map-gen-settings",
            str(native_root / "map-gen-settings.json"),
        ],
        native_config,
        Path(f"{log_prefix}-native-create.log"),
    )
    require(save.is_file(), "Native engine did not create its reference save")
    benchmark_args = [
        "--benchmark",
        str(save),
        "--benchmark-ticks",
        "120",
        "--benchmark-runs",
        "1",
    ]
    native_log = run_logged(
        prefix,
        benchmark_args,
        native_config,
        Path(f"{log_prefix}-native-benchmark.log"),
    )
    checksum = benchmark_checksum(native_log)
    if args.mode == "space-age":
        output = run_logged(
            prefix,
            ["--test-scenario", "port-validation"],
            native_config,
            Path(f"{log_prefix}-native-expansion.log"),
        )
        require(
            "FACTORIO_PORT_EXPANSION_TEST: PASS" in output,
            "Native expansion scenario did not pass",
        )
    report = {
        "source_profile": profile.key,
        "mode": args.mode,
        "native_checksum": checksum,
        "simulator_checked": False,
    }
    if args.simulator:
        app_container = Path(
            subprocess.check_output(
                [
                    "xcrun",
                    "simctl",
                    "get_app_container",
                    args.simulator,
                    args.bundle_id,
                    "app",
                ],
                text=True,
            ).strip()
        )
        info = plistlib.loads((app_container / "Info.plist").read_bytes())
        require(
            info.get("FactorioSourceProfile") == profile.key,
            "Installed simulator app is from another source profile",
        )
        user_container = Path(
            subprocess.check_output(
                [
                    "xcrun",
                    "simctl",
                    "get_app_container",
                    args.simulator,
                    args.bundle_id,
                    "data",
                ],
                text=True,
            ).strip()
        )
        simulator_root = user_container / "Documents/Factorio/validation" / label
        config = prepare_probe(
            simulator_root, app_container / "data", profile, args.mode
        )
        simulator_save = simulator_root / "probe-map.zip"
        shutil.copyfile(save, simulator_save)
        prefix = [
            "xcrun",
            "simctl",
            "launch",
            "--console",
            "--terminate-running-process",
            args.simulator,
            args.bundle_id,
        ]
        arguments = [
            "--benchmark",
            str(simulator_save),
            "--benchmark-ticks",
            "120",
            "--benchmark-runs",
            "1",
        ]
        output = run_logged(
            prefix, arguments, config, Path(f"{log_prefix}-simulator-benchmark.log")
        )
        require(
            benchmark_checksum(output) == checksum,
            "Native and simulator checksums differ",
        )
        if args.mode == "space-age":
            output = run_logged(
                prefix,
                ["--test-scenario", "port-validation"],
                config,
                Path(f"{log_prefix}-simulator-expansion.log"),
            )
            require(
                "FACTORIO_PORT_EXPANSION_TEST: PASS" in output,
                "Simulator expansion scenario did not pass",
            )
        report.update({"simulator_checked": True, "simulator_checksum": checksum})
    Path(f"{log_prefix}.json").write_text(json.dumps(report, indent=2) + "\n")
    logger.info("%s", json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
