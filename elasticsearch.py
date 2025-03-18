import requests
import sys
import json
import urllib3
import random
import string
import argparse
from colorama import Fore, Style, init

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Enable colored output
init(autoreset=True)

def build_url(protocol, ip, port, path):
    return f"{protocol}://{ip}:{port}/{path.lstrip('/')}"

def get_cluster_health(protocol, ip, port):
    try:
        r = requests.get(build_url(protocol, ip, port, "/_cluster/health"), verify=False, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"{Fore.RED}[!] Error getting cluster health: {e}")
        return {}

def get_cluster_stats(protocol, ip, port):
    try:
        r = requests.get(build_url(protocol, ip, port, "/_cluster/stats"), verify=False, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"{Fore.RED}[!] Error getting cluster stats: {e}")
        return {}

def list_indices(protocol, ip, port):
    try:
        r = requests.get(build_url(protocol, ip, port, "/_cat/indices?format=json&bytes=mb"), verify=False, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"{Fore.RED}[!] Error listing indices: {e}")
        return []

def dump_index(protocol, ip, port, index, limit=5):
    try:
        r = requests.post(
            build_url(protocol, ip, port, f"/{index}/_search"),
            json={"size": limit, "query": {"match_all": {}}},
            verify=False,
            timeout=5
        )
        r.raise_for_status()
        return r.json().get("hits", {}).get("hits", [])
    except Exception as e:
        print(f"{Fore.RED}[!] Error dumping index '{index}': {e}")
        return []

def create_synack_index(protocol, ip, port):
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    index_name = f"synack-{random_suffix}"
    url = build_url(protocol, ip, port, f"/{index_name}")

    try:
        r = requests.put(url, verify=False, timeout=5)
        if r.status_code in [200, 201]:
            print(f"\n{Fore.GREEN}[+] Successfully created index: {index_name}")
            return index_name
        else:
            print(f"{Fore.YELLOW}[-] Could not create index (might be read-only): {r.status_code} - {r.text}")
    except Exception as e:
        print(f"{Fore.RED}[!] Error creating index: {e}")
    return None

def print_cluster_info(health, stats):
    print(f"\n{Fore.CYAN}====== Cluster Overview ======")
    status_color = {
        "green": Fore.GREEN,
        "yellow": Fore.YELLOW,
        "red": Fore.RED
    }.get(health.get("status", "").lower(), Fore.WHITE)

    print(f"{Fore.WHITE}Cluster Name      : {Fore.LIGHTWHITE_EX}{health.get('cluster_name', 'N/A')}")
    print(f"{Fore.WHITE}Status            : {status_color}{health.get('status', 'N/A').upper()}")
    print(f"{Fore.WHITE}Number of Nodes   : {Fore.LIGHTWHITE_EX}{health.get('number_of_nodes', 'N/A')}")
    print(f"{Fore.WHITE}Number of Indices : {Fore.LIGHTWHITE_EX}{stats.get('indices', {}).get('count', 'N/A')}")
    print(f"{Fore.WHITE}Total Docs        : {Fore.LIGHTWHITE_EX}{stats.get('indices', {}).get('docs', {}).get('count', 'N/A')}")
    size_mb = stats.get('indices', {}).get('store', {}).get('size_in_bytes', 0) / (1024**2)
    print(f"{Fore.WHITE}Total Size        : {Fore.LIGHTWHITE_EX}{size_mb:.2f} MB")

def print_all_indices(indices):
    print(f"\n{Fore.MAGENTA}====== All Indices ======")
    print(f"{Fore.YELLOW}{'Index Name':40} {'Docs':>10} {'Size (MB)':>10} {'Status':>10}")
    print(f"{'-'*75}")
    for idx in indices:
        name = idx.get("index", "")
        docs = idx.get("docs.count", "0")
        size = idx.get("store.size", "0")
        status = idx.get("health", "unknown").upper()
        status_color = {
            "GREEN": Fore.GREEN,
            "YELLOW": Fore.YELLOW,
            "RED": Fore.RED
        }.get(status, Fore.WHITE)
        print(f"{Fore.LIGHTWHITE_EX}{name:40} {docs:>10} {size:>10} {status_color}{status:>10}")

def main():
    parser = argparse.ArgumentParser(description="Elasticsearch Cluster Reporter & Access Tester")
    parser.add_argument("--ip", required=True, help="Target IP address (e.g., 192.168.1.100)")
    parser.add_argument("--port", required=True, help="Port number (e.g., 9200)")
    parser.add_argument("--ssl", action="store_true", help="Use HTTPS instead of HTTP")
    args = parser.parse_args()

    protocol = "https" if args.ssl else "http"
    ip = args.ip
    port = args.port

    print(f"{Fore.CYAN}[*] Connecting to Elasticsearch at {protocol}://{ip}:{port}...\n")

    health = get_cluster_health(protocol, ip, port)
    stats = get_cluster_stats(protocol, ip, port)

    # Try to create synack-* index
    create_synack_index(protocol, ip, port)

    # Refresh index list after attempted creation
    indices = list_indices(protocol, ip, port)
    if not indices:
        print(f"{Fore.RED}[!] No indices found or unable to connect.")
        return

    print_cluster_info(health, stats)
    print_all_indices(indices)

    print(f"\n{Fore.CYAN}====== Top 5 Indices Sample Dump ======")
    for idx in indices[:5]:
        index_name = idx.get("index")
        print(f"\n{Fore.LIGHTBLUE_EX}--- Index: {index_name} ---")
        docs = dump_index(protocol, ip, port, index_name)
        for i, doc in enumerate(docs, 1):
            print(f"{Fore.LIGHTGREEN_EX}\nDocument {i}:")
            print(json.dumps(doc.get("_source", doc), indent=2))

if __name__ == "__main__":
    main()
