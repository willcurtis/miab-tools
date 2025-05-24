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
    print("\u2705 .env file created/updated successfully.")

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

def extend_records_with_source_tag(custom_records, external_records=None):
    for r in custom_records:
        r["source"] = "custom"
    if external_records:
        for r in external_records:
            r["source"] = "external"
        return custom_records + external_records
    return custom_records

class MailInABoxDNSBasicAuth:
    def __init__(self, host, email, password):
        self.base_url = f"https://{host}/admin"
        self.session = requests.Session()
        self.session.auth = (email, password)

    def list_records(self):
        return self._get("/dns/custom")

    def get_external_zonefile(self, zone):
        return self._get(f"/dns/zonefile-external/{zone}")

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

def get_combined_records(dns, domain_filter=None, qname=None, rtype=None):
    custom = dns.list_records()
    try:
        external = dns.get_external_zonefile(domain_filter or (qname.split(".", 1)[-1] if qname else None))
    except Exception:
        external = []
    all_records = extend_records_with_source_tag(custom, external)
    if domain_filter:
        return filter_records_by_domain(all_records, domain_filter)
    if qname and rtype:
        return [r for r in all_records if r["qname"] == qname and r["rtype"] == rtype]
    return all_records

def print_pretty(command, result):
    if command in ("list-records", "get-record", "get-zonefile"):
        show_source = any("source" in r for r in result)
        headers = ["Name", "Type", "Value"] + (["Source"] if show_source else [])
        table = [
            [r["qname"], r["rtype"], r["value"]] + ([r.get("source")] if show_source else [])
            for r in result
        ]
        print(tabulate(table, headers=headers, tablefmt="fancy_grid"))
    elif command in ("add-record", "update-record", "remove-record"):
        print(f"\u2705 {result['message']}")
    elif command == "list-zones":
        print(tabulate([[z] for z in result], headers=["Zone"], tablefmt="grid"))
    elif command == "get-secondary-ns":
        print(tabulate([[ns] for ns in result], headers=["Secondary Nameserver"], tablefmt="grid"))
    elif command == "update-dns":
        print(json.dumps(result, indent=2))
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
        description="\U0001F4EC Mail-in-a-Box DNS CLI Tool",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list-records", help="List all DNS records, or filter by domain")
    list_parser.add_argument("domain", nargs="?", help="Filter by domain (optional)")
    list_parser.add_argument("--external", action="store_true", help="Include external (system) records")

    get_parser = subparsers.add_parser("get-record", help="Get a DNS record by name and type")
    get_parser.add_argument("qname")
    get_parser.add_argument("rtype")
    get_parser.add_argument("--external", action="store_true", help="Include external (system) records")

    add_parser = subparsers.add_parser("add-record", help="Add a DNS record")
    add_parser.add_argument("qname")
    add_parser.add_argument("rtype")
    add_parser.add_argument("value")
    add_parser.add_argument("-u", "--update", action="store_true", help="Update if it exists")

    update_parser = subparsers.add_parser("update-record", help="Force update a DNS record")
    update_parser.add_argument("qname")
    update_parser.add_argument("rtype")
    update_parser.add_argument("value")

    delete_parser = subparsers.add_parser("remove-record", help="Remove a DNS record")
    delete_parser.add_argument("qname")
    delete_parser.add_argument("rtype")

    subparsers.add_parser("list-zones", help="List all zones")

    zonefile_parser = subparsers.add_parser("get-zonefile", help="Get custom zonefile (default)")
    zonefile_parser.add_argument("zone")
    zonefile_parser.add_argument("--external", action="store_true", help="Include external records")

    updatedns_parser = subparsers.add_parser("update-dns", help="Trigger DNS update")
    updatedns_parser.add_argument("--force", action="store_true")

    subparsers.add_parser("get-secondary-ns", help="List secondary nameservers")

    addns_parser = subparsers.add_parser("add-secondary-ns", help="Add secondary nameservers")
    addns_parser.add_argument("hostnames", help="Comma-separated list of NS")

    args = parser.parse_args()

    try:
        host, email, password = load_credentials()
        dns = MailInABoxDNSBasicAuth(host, email, password)

        if args.command == "list-records":
            result = get_combined_records(dns, domain_filter=args.domain) if args.external else dns.list_records()

        elif args.command == "get-record":
            result = get_combined_records(dns, qname=args.qname, rtype=args.rtype) if args.external else dns.get_record(args.qname, args.rtype)

        elif args.command == "add-record":
            records = dns.list_records()
            existing = find_existing_record(records, args.qname)
            if any(r["rtype"] == args.rtype for r in existing):
                print("\u26a0\ufe0f Existing record(s) for this name:")
                print_pretty("list-records", existing)
                if args.update or prompt_yes_no("Do you want to update this record? [y/N]"):
                    for r in existing:
                        if r["rtype"] == args.rtype:
                            dns.remove_record(r["qname"], r["rtype"])
                    result = dns.add_record(args.qname, args.rtype, args.value)
                else:
                    print("\u274c Record was not added or updated.")
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
            custom = dns.get_zonefile(args.zone)
            external = []
            if args.external:
                try:
                    external = dns.get_external_zonefile(args.zone)
                except:
                    print("\u26a0\ufe0f No external records found or supported.")
            result = extend_records_with_source_tag(custom, external)

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
