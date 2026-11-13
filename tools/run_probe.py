"""Run original engine CLI experiments with data copied into the simulator sandbox."""

import argparse
import json
import re
import subprocess
from pathlib import Path

from audit import DEFAULT_APP, ROOT
from bundle_assets import sync_assets
from config import source_profile

DEVICE = "booted"
BUNDLE = "local.factorio.loaderprobe"


def main() -> None:
    """Run an isolated simulator CLI probe using the selected executable's data."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", choices=["version", "help", "create", "benchmark", "preview", "gui"]
    )
    parser.add_argument("--device", default=DEVICE)
    parser.add_argument("--bundle-id", default=BUNDLE)
    parser.add_argument("--app", type=Path, default=DEFAULT_APP)
    parser.add_argument("--game-mode", choices=["base", "space-age"])
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    profile = source_profile(args.app)
    game_mode = args.game_mode or profile.edition
    if game_mode == "space-age" and profile.edition != "space-age":
        parser.error("Space Age requires the analyzed expansion executable")
    (ROOT / "build").mkdir(exist_ok=True)
    (ROOT / "reports").mkdir(exist_ok=True)
    root = (
        Path(
            subprocess.check_output(
                [
                    "xcrun",
                    "simctl",
                    "get_app_container",
                    args.device,
                    args.bundle_id,
                    "data",
                ],
                text=True,
            ).strip()
        )
        / "Documents/Factorio"
    )
    root.mkdir(parents=True, exist_ok=True)
    userdata = root / "user"
    userdata.mkdir(exist_ok=True)
    if args.mode not in ("version", "help"):
        sync_assets(args.app / "Contents/data", root / "data", profile.sha256)
    mods = root / "probe-mods" / profile.key / game_mode
    mods.mkdir(parents=True, exist_ok=True)
    (mods / "mod-list.json").write_text(
        json.dumps(
            {
                "mods": [
                    {
                        "name": name,
                        "enabled": name == "base" or game_mode == "space-age",
                    }
                    for name, _ in profile.mods
                    if name != "core"
                ]
            },
            indent=2,
        )
        + "\n"
    )
    config = root / "config.ini"
    config.write_text(
        f"[path]\nread-data={root / 'data'}\nwrite-data={userdata}\n[general]\ncheck-updates=false\n"
        "[graphics]\ntexture-compression-level=none\ncompress-virtual-atlas=false\n"
        "gpu-accelerated-compression=false\ngpu-accelerated-mipmap-compression=false\n"
        "video-memory-usage=low\nmax-sprite-loading-threads=2\n"
    )
    settings = root / "map-gen-settings.json"
    settings.write_text(json.dumps({"width": 64, "height": 64, "seed": 12345}))
    save = userdata / "probe-map.zip"
    params = {
        "version": ["--version"],
        "help": ["--help"],
        "create": ["--create", str(save), "--map-gen-settings", str(settings)],
        "benchmark": [
            "--benchmark",
            str(save),
            "--benchmark-ticks",
            "120",
            "--benchmark-runs",
            "1",
        ],
        "preview": [
            "--generate-map-preview",
            str(userdata / "map-preview.png"),
            "--map-preview-size",
            "256",
            "--map-gen-settings",
            str(settings),
            "--threads",
            "2",
        ],
        "gui": [
            "--force-metal",
            "--window-size",
            "1194x834",
            "--graphics-quality",
            "medium",
        ],
    }[args.mode]
    if args.mode not in ("version", "help"):
        params += [
            "--config",
            str(config),
            "--mod-directory",
            str(mods),
            "--disable-audio",
            "--nogamepad",
        ]
    command = [
        "xcrun",
        "simctl",
        "launch",
        "--console",
        "--terminate-running-process",
        args.device,
        args.bundle_id,
    ] + params
    logfile = ROOT / f"reports/{args.mode}-simulator.log"
    print("Sandbox:", root, flush=True)
    print("Log:", logfile, flush=True)
    if args.debug:
        command.remove("--console")
        command.insert(3, "--wait-for-debugger")
        launch = subprocess.check_output(command, text=True, stderr=subprocess.STDOUT)
        print(launch, flush=True)
        match = re.search(r": (\d+)\s*$", launch)
        if match is None:
            raise RuntimeError(
                f"Simulator launch did not report a process identifier: {launch}"
            )
        pid = int(match.group(1))
        script = ROOT / "build/debug.lldb"
        script.write_text(
            f"process attach --pid {pid}\nprocess handle SIGSEGV -s true -n false -p false\nprocess handle SIGABRT -s true -n false -p false\ncontinue\nthread backtrace\nregister read\ndisassemble --frame\nprocess detach\n"
        )
        with (ROOT / "reports/debugger.log").open("w") as log:
            subprocess.run(
                ["xcrun", "lldb", "--batch", "--source", str(script)],
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=60,
                check=True,
            )
        print((ROOT / "reports/debugger.log").read_text())
        return
    try:
        with logfile.open("wb") as log:
            completed = subprocess.run(
                command, stdout=log, stderr=subprocess.STDOUT, timeout=90, check=False
            )
        status = completed.returncode
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["xcrun", "simctl", "terminate", args.device, args.bundle_id],
            capture_output=True,
            check=False,
        )
        with logfile.open("ab") as log:
            log.write(b"\nPROBE_RUNNER_TIMEOUT\n")
        status = 124
    output = logfile.read_bytes()
    print(output.decode(errors="replace"))
    print("simctl exit:", status)
    if args.mode == "create":
        print(
            "Save exists:",
            save.exists(),
            "bytes:",
            save.stat().st_size if save.exists() else 0,
        )
        if not save.exists():
            status = status or 1
        else:
            import shutil

            shutil.copyfile(save, ROOT / "build/probe-map.zip")
    if args.mode == "preview" and (userdata / "map-preview.png").exists():
        import shutil

        shutil.copyfile(userdata / "map-preview.png", ROOT / "reports/map-preview.png")
    if b"FACTORIO_PROBE_UNIMPLEMENTED:" in output or b"Factorio crashed." in output:
        status = status or 1
    # simctl may report 0 even if a child aborts; inspect logs and artifacts too.
    raise SystemExit(status)


if __name__ == "__main__":
    main()
