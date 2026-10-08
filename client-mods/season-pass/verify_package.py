"""Verify a complete prepared Season Pass client package."""
import argparse
import sys
from pathlib import Path
from verify_standalone import verify

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package',type=Path)
    args=parser.parse_args()
    try:
        verify(args.package)
    except Exception as error:
        print('FAIL:',error)
        sys.exit(1)
