"""burn-severity: several burn-severity maps of one fire, put on one grid and compared.

    uv run python -m burn_severity perimeter perry-2025
    uv run python -m burn_severity ours perry-2025 initial|extended
    uv run python -m burn_severity official perry-2025 ~/Downloads/<bundle>.zip [...]
    uv run python -m burn_severity compare perry-2025 [reference-map]
    uv run python -m burn_severity calibrate perry-2025
"""
import json
import sys
from pathlib import Path

from .fire import load


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        raise SystemExit(__doc__)
    cmd, fire = argv[0], load(argv[1])
    if cmd == "perimeter":
        g = fire.perimeter()
        print(f"{fire.id}: {g.area.sum() / 4046.86:,.0f} acres")
    elif cmd == "ours":
        from .s2 import estimate
        info = estimate(fire, argv[2])
        log = fire.data / "ours-runs.json"
        runs = json.loads(log.read_text()) if log.exists() else {}
        runs[argv[2]] = info
        log.write_text(json.dumps(runs, indent=1))
        print(info)
    elif cmd == "official":
        from .others import official
        print(official(fire, [Path(p).expanduser() for p in argv[2:]]))
    elif cmd == "calibrate":
        from .calibrate import calibrate
        print(json.dumps(calibrate(fire), indent=1))
    elif cmd == "compare":
        from .compare import compare
        print(compare(fire, argv[2] if len(argv) > 2 else None).to_string(index=False))
    else:
        raise SystemExit(__doc__)


main(sys.argv[1:])
