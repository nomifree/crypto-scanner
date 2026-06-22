import argparse
import os


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Operation Mizan scanner")
    parser.add_argument(
        "--mode",
        choices=["crypto", "pmex", "psx", "markets", "all", "crypto_pmex"],
        help="Override SCAN_MODE for this run.",
    )
    args = parser.parse_args()
    if args.mode:
        os.environ["SCAN_MODE"] = args.mode
    from crypto_scanner.runner import main

    main()
