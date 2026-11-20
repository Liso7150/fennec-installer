"""Auto-update system for fennec-installer"""

import hashlib
import platform
import shutil
import sys
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
import urllib.request
import json

GITHUB_REPO = "Liso7150/fennec-installer"


@dataclass
class Asset:
    name: str
    download_url: str
    size: int


@dataclass
class Release:
    version: str
    tag: str
    published_at: str
    assets: List[Asset]
    checksums_url: Optional[str] = None


def get_platform() -> tuple[str, str]:
    system = platform.system().lower()
    machine = platform.machine().lower()
    os_name = {"windows": "windows", "darwin": "macos", "linux": "linux"}.get(system, system)
    arch = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}.get(machine, machine)
    return os_name, arch


def check_stable(current_version: str) -> Optional[Release]:
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "fennec-updater"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 404:
                return None
            data = json.loads(resp.read().decode())
    except Exception as e:
        raise Exception(f"GitHub API: {e}")
    
    tag = data.get("tag_name", "")
    version = tag.lstrip("v")
    if version <= current_version:
        return None
    
    assets = [Asset(name=a["name"], download_url=a["browser_download_url"], size=a["size"]) for a in data.get("assets", [])]
    checksums_url = next((a["browser_download_url"] for a in data.get("assets", []) if "checksum" in a["name"].lower()), None)
    
    return Release(version=version, tag=tag, published_at=data.get("published_at", ""), assets=assets, checksums_url=checksums_url)


def check_experimental() -> Optional[Release]:
    url = f"https://api.github.com/repos/{GITHUB_REPO}/commits/main"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "fennec-updater"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        raise Exception(f"GitHub API: {e}")
    
    sha = data.get("sha", "")
    return Release(version=f"dev-{sha[:7]}", tag=sha, published_at=data.get("commit", {}).get("author", {}).get("date", ""), assets=[], checksums_url=None)


def download_asset(url: str, expected_checksum: Optional[str] = None) -> bytes:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "fennec-updater"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = resp.read()
    except Exception as e:
        raise Exception(f"Download: {e}")
    
    if expected_checksum:
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected_checksum:
            raise Exception(f"Checksum mismatch: expected {expected_checksum}, got {actual}")
    
    return data


def update(experimental: bool = False) -> str:
    from bootstrap import VERSION as current
    
    if experimental:
        print("[update] Checking experimental channel (main branch)...")
        release = check_experimental()
        if release is None:
            return "Already on latest experimental build"
        print(f"[update] New commit available: {release.version}")
        return f"Experimental update available: {release.version}"
    else:
        print("[update] Checking stable releases...")
        release = check_stable(current)
        if release is None:
            return f"Already on latest version ({current})"
        
        print(f"[update] New version available: {release.version} (current: {current})")
        
        os_name, arch = get_platform()
        name = f"fennec-installer-{os_name}-{arch}.py" if os_name != "windows" else f"fennec-installer-{os_name}-{arch}.exe"
        asset = next((a for a in release.assets if a.name == name), None)
        
        if asset is None:
            return f"No asset for platform: {name}"
        
        print(f"[update] Downloading {name}...")
        data = download_asset(asset.download_url)
        
        current_exe = Path(sys.executable if hasattr(sys, 'frozen') else __file__)
        temp_path = current_exe.with_suffix(current_exe.suffix + ".new")
        temp_path.write_bytes(data)
        
        return f"Updated to {release.version} - new version at {temp_path}"


if __name__ == "__main__":
    experimental = "--experimental" in sys.argv
    try:
        result = update(experimental)
        print(f"[update] {result}")
    except Exception as e:
        print(f"[update] Error: {e}", file=sys.stderr)
        sys.exit(1)
