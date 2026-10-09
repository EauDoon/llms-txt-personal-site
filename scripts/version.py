"""The template's release version, written down in this one place.

    python scripts/version.py          print the version

Every CLI's --version, the live checker's User-Agent and the generator field
of content-manifest.json read it from here. The file-format versions inside
the manifest, the review reports and the eval data are separate and stay 1.
"""
import argparse

PROJECT = "llms-txt-personal-site"
__version__ = "1.0.0-dev"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    parser.parse_args(argv)
    print(__version__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
