"""Prepare the complete Season Pass integration for the supported original Aion 4.8 NA client."""
import argparse
import hashlib
from pathlib import Path
from standalone import prepare

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--server-url',default='http://127.0.0.1:8091',help='Public HTTPS origin, or loopback when client and server share a PC')
    args=parser.parse_args()
    prepare(args.client,args.output,args.server_url)

if __name__=='__main__':
    main()
