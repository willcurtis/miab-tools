#!/usr/bin/env python3

import requests
import json
import os
import sys
import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv, set_key
from tabulate import tabulate

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
ENV_PATH = Path(".env")

def load_credentials():
    load_dotenv(dotenv_path=ENV_PATH)
    email = os.getenv("MIAB_EMAIL")
    password = os.getenv("MIAB_PASSWORD")
    host = os.getenv("MIAB_HOST")
    if not all([email, password, host]):
        raise ValueError("MIAB_HOST, MIAB_EMAIL, and MIAB_PASSWORD must be set in .env")
    return host, email, password

def create_env_file(host, email, password):
    if not ENV_PATH.exists():
        ENV_PATH.touch()
    set_key(ENV_PATH, "MIAB_HOST", host)
    set_key(ENV_PATH, "MIAB_EMAIL", email)
    set_key(ENV_PATH, "MIAB_PASSWORD", password)
    print("✅ .env file created/updated successfully.")

def prompt_yes_no(message):
    try:
        answer = input(message + " ").strip().lower()
        return answer in ("y", "yes")
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)

def find_existing_record(records, qname):
    return [r for r in records if r["qname"] == qname]

def filter_records_by_domain(records, domain):
    return [r for r in records if r["qname"].endswith(domain)]

class MailInABoxDNSBasicAuth:
    def __init__(self, host, email, password):
        self.base_url = f"https://{host}/admin"
        self.session = requests.Session()
        self.session.auth = (email, password)

    def list_records(self):
        return self._get("/dns/custom")

    def get_record(self, qname, rtype):
        return [r for r in self.list_records() if r["qname"] == qname and r["rtype"] == rtype]

    def add_record(self, qname, rtype, value):
        url = f"{self.base_url}/dns/custom/{qname}/{rtype}"
        headers = {"Content-Type": "text/plain"}
        response = self.session.post(url, headers=headers, data=value.strip())
        response.raise_for_status()
        return {"message": "Record added or updated."}

    def update_record(self, qname, rtype, value):
        existing = self.get_record(qname, rtype)
        for r in existing:
            self.remove_record(r["qname"], r["rtype"])
        return self.add_record(qname, rtype, value)

    def remove_record(self, qname, rtype):
        url = f"{self.base_url}/dns/custom/{qname}/{rtype}"
        response = self.session.delete(url)
        response.raise_for_status()
        return {"message": "Record deleted."}

    def list_zones(self):
        return self._get("/dns/zones")

    def get_zonefile(self, zone):
        return self._get(f"/dns/zones/{zone}")

    def update_dns(self, force=False):
        return self._post("/dns/update", {"force": str(force).lower()})

    def get_secondary_nameservers(self):
        return self._get("/dns/secondary_nameservers")

    def add_secondary_nameservers(self, hostnames):
        return self._post("/dns/secondary_nameservers", {"hostnames": hostnames})

    def _get(self, endpoint):
        resp = self.session.get(self.base_url + endpoint)
        resp.raise_for_status()
        return resp.json()

    def _post(self, endpoint, data):
        resp = self.session.post(self.base_url + endpoint, data=data)
        resp.raise_for_status()
        return resp.json()

def print_pretty(command, result):
    if command in ("list-records", "get-record"):
        table = [[r["qname"], r["rtype"], r["value"]] for r in result]
        print(tabulate(table, headers=["Name", "Type", "Value"], tablefmt="fancy_grid"))
    elif command in ("add-record", "update-record", "remove-record"):
        print(f"✅ {result['message']}")
    elif command == "list-zones":
        print(tabulate([[z] for z in result], headers=["Zone"], tablefmt="grid"))
    elif command == "get-secondary-ns":
        print(tabulate([[ns] for ns in result], headers=["Secondary Nameserver"], tablefmt="grid"))
    elif command == "update-dns":
        print(json.dumps(result, indent=2))
    elif command == "get-zonefile":
        print(result)
    else:
        print(json.dumps(result, indent=2))

def cli_main():
    if "--setup-env" in sys.argv:
        host = input("MIAB host (e.g. box.example.com): ")
        email = input("MIAB email: ")
        password = input("MIAB password: ")
        create_env_file(host, email, password)
        print("Run the script again with a command.")
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="📬 Mail-in-a-Box DNS CLI Tool",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser(
        "list-records",
        help="List all DNS records, or filter by domain"
    )
    list_parser.add_argument("domain", nargs="?", help="Filter by domain (optional)")

    get_parser = subparsers.add_parser(
        "get-record",
        help="Get a specific DNS record by name and type"
    )
    get_parser.add_argument("qname", help="Fully qualified record name")
    get_parser.add_argument("rtype", help="Record type (e.g. A, CNAME, TXT)")

    add_parser = subparsers.add_parser(
        "add-record",
        help="Add a DNS record (asks to overwrite if already exists)"
    )
    add_parser.add_argument("qname")
    add_parser.add_argument("rtype")
    add_parser.add_argument("value")
    add_parser.add_argument("-u", "--update", action="store_true", help="Update record if it already exists")

    update_parser = subparsers.add_parser(
        "update-record",
        help="Force update a DNS record by replacing existing"
    )
    update_parser.add_argument("qname")
    update_parser.add_argument("rtype")
    update_parser.add_argument("value")

    delete_parser = subparsers.add_parser(
        "remove-record",
        help="Remove a DNS record by name and type"
    )
    delete_parser.add_argument("qname")
    delete_parser.add_argument("rtype")

    subparsers.add_parser(
        "list-zones",
        help="List all configured DNS zones"
    )

    zonefile_parser = subparsers.add_parser(
        "get-zonefile",
        help="Get full zone file contents"
    )
    zonefile_parser.add_argument("zone", help="Zone domain name (e.g. example.com)")

    updatedns_parser = subparsers.add_parser(
        "update-dns",
        help="Trigger a DNS configuration update"
    )
    updatedns_parser.add_argument("--force", action="store_true", help="Force DNS update")

    subparsers.add_parser(
        "get-secondary-ns",
        help="List secondary nameservers"
    )

    addns_parser = subparsers.add_parser(
        "add-secondary-ns",
        help="Add secondary nameservers"
    )
    addns_parser.add_argument("hostnames", help="Comma-separated list of secondary NS hostnames")

    args = parser.parse_args()

    try:
        host, email, password = load_credentials()
        dns = MailInABoxDNSBasicAuth(host, email, password)

        if args.command == "list-records":
            records = dns.list_records()
            result = filter_records_by_domain(records, args.domain) if args.domain else records

        elif args.command == "get-record":
            result = dns.get_record(args.qname, args.rtype)

        elif args.command == "add-record":
            records = dns.list_records()
            existing = find_existing_record(records, args.qname)
            if any(r["rtype"] == args.rtype for r in existing):
                print("⚠️ Existing record(s) for this name:")
                print_pretty("list-records", existing)
                if args.update or prompt_yes_no("Do you want to update this record? [y/N]"):
                    for r in existing:
                        if r["rtype"] == args.rtype:
                            dns.remove_record(r["qname"], r["rtype"])
                    result = dns.add_record(args.qname, args.rtype, args.value)
                else:
                    print("❌ Record was not added or updated.")
                    return
            else:
                result = dns.add_record(args.qname, args.rtype, args.value)

        elif args.command == "update-record":
            result = dns.update_record(args.qname, args.rtype, args.value)

        elif args.command == "remove-record":
            result = dns.remove_record(args.qname, args.rtype)

        elif args.command == "list-zones":
            result = dns.list_zones()

        elif args.command == "get-zonefile":
            result = dns.get_zonefile(args.zone)

        elif args.command == "update-dns":
            result = dns.update_dns(force=args.force)

        elif args.command == "get-secondary-ns":
            result = dns.get_secondary_nameservers()

        elif args.command == "add-secondary-ns":
            result = dns.add_secondary_nameservers(args.hostnames)

        else:
            parser.print_help()
            sys.exit(0)

        print_pretty(args.command, result)

    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(str(e))
        sys.exit(1)

if __name__ == "__main__":
    cli_main()
