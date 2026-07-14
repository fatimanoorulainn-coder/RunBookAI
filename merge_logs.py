"""One-off: fold real Loghub OpenStack lines into the log as searchable noise."""
import random
from pathlib import Path

LOGS = Path(__file__).resolve().parent / "data" / "logs"
SIGNAL = LOGS / "openstack_sandbox.log"
NOISE = LOGS / "openstack_noise.log"
BACKUP = LOGS / "openstack_sandbox.log.bak"


def main() -> None:
    signal = [l.rstrip("\n") for l in SIGNAL.read_text(encoding="utf-8").splitlines() if l.strip()]
    noise = [l.rstrip("\n") for l in NOISE.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(signal) > 200:
        raise SystemExit(f"{SIGNAL.name} already has {len(signal)} lines - looks merged.")
    BACKUP.write_text("\n".join(signal) + "\n", encoding="utf-8")
    combined = signal + noise
    random.seed(42)
    random.shuffle(combined)
    SIGNAL.write_text("\n".join(combined) + "\n", encoding="utf-8")
    print(f"backed up {len(signal)} tagged lines -> {BACKUP.name}")
    print(f"wrote {len(combined)} lines ({len(signal)} signal + {len(noise)} noise) -> {SIGNAL.name}")


if __name__ == "__main__":
    main()