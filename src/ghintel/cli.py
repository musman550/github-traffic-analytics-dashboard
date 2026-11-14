import json, sys
from .store import load


def main():
    cfg = load("config/config.json")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("collect", "all"):
        from .collector import collect
        collect(cfg)
    if cmd in ("build", "all"):
        from .aggregator import build_summary
        from .site import build_all
        build_summary(cfg)
        build_all(cfg)
        print("built summary + site")


if __name__ == "__main__":
    main()
