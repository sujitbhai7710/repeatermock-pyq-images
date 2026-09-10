#!/usr/bin/env python3
"""Upload PYQ images from source repo to this repo via GitHub API."""
import json, os, time, base64, urllib.request, urllib.parse, httpx, sys
from datetime import datetime, timezone

SOURCE_REPO = "sujitbhai7710/repeatermock-mass-scraper"
TARGET_REPO = os.environ.get("GITHUB_REPOSITORY", "sujitbhai7710/repeatermock-pyq-images")
GH_TOKEN = os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", ""))

SERIES_MAP = [
    ("SSC-CGL-2026", "SSC-CGL"),
    ("SSC-CHSL-2025", "SSC-CHSL"),
    ("SSC-CPO-2026", "SSC-CPO"),
    ("SSC-GD-2026", "SSC-GD"),
    ("SSC-MTS-2026", "SSC-MTS"),
    ("SSC-SelPost-2026", "SSC-Selection-Post"),
    ("SSC-Steno-2026", "SSC-Stenographer"),
]

START_TIME = time.time()
MAX_RUNTIME = 5.4 * 3600

def gh_api(url, token=None):
    """Make authenticated GitHub API request."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Mozilla/5.0"}
    if token:
        headers["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())

def list_images(series_folder):
    """List all PNG files in series images/ folder using contents API with pagination."""
    all_images = []
    path = f"scraped_output/{series_folder}/images"
    for page in range(1, 500):
        encoded = urllib.parse.quote(path)
        url = f"https://api.github.com/repos/{SOURCE_REPO}/contents/{encoded}?per_page=100&page={page}"
        try:
            items = gh_api(url, token=GH_TOKEN)
        except Exception as e:
            if page == 1:
                print(f"    Error: {e}")
            break
        if not isinstance(items, list) or len(items) == 0:
            break
        for item in items:
            if item['type'] == 'file' and item['name'].endswith('.png'):
                all_images.append(item['name'])
        if len(items) < 100:
            break
        time.sleep(0.5)  # Rate limit
    return all_images

def download_image(series_folder, image_name):
    path = f"scraped_output/{series_folder}/images/{image_name}"
    encoded = urllib.parse.quote(path)
    url = f"https://raw.githubusercontent.com/{SOURCE_REPO}/main/{encoded}"
    with httpx.Client(timeout=30) as cli:
        r = cli.get(url)
        if r.status_code == 200:
            return r.content
    return None

def upload_image(series_target, image_name, content):
    path = f"{series_target}/images/{image_name}"
    url = f"https://api.github.com/repos/{TARGET_REPO}/contents/{urllib.parse.quote(path)}"
    data = json.dumps({
        "message": f"Add: {series_target}/images/{image_name}",
        "content": base64.b64encode(content).decode(),
    }).encode()
    req = urllib.request.Request(url, data=data, method="PUT", headers={
        "Authorization": f"token {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return True
    except:
        return False

total_uploaded = 0
total_skipped = 0
total_failed = 0

print(f"Target: {TARGET_REPO}")
print(f"Token: {'✅' if GH_TOKEN else '❌'}")
print(f"Max runtime: 5.4 hours")

for si, (series_folder, series_target) in enumerate(SERIES_MAP):
    elapsed = time.time() - START_TIME
    if elapsed >= MAX_RUNTIME:
        print(f"\n⏰ Max runtime - stopping")
        break
    
    print(f"\n--- {si+1}/7: {series_target}/images/ ---")
    print(f"  Listing images...", flush=True)
    images = list_images(series_folder)
    print(f"  Found {len(images)} images", flush=True)
    
    if not images:
        print(f"  ⚠️ No images found - skipping")
        continue
    
    for img in images:
        elapsed = time.time() - START_TIME
        if elapsed >= MAX_RUNTIME:
            print(f"\n⏰ Time limit reached")
            break
        
        content = download_image(series_folder, img)
        if not content:
            total_failed += 1
            continue
        
        if upload_image(series_target, img, content):
            total_uploaded += 1
        else:
            total_failed += 1
        
        if (total_uploaded + total_failed) % 50 == 0:
            print(f"  📤 {total_uploaded} uploaded, {total_failed} failed", flush=True)
        
        time.sleep(0.3)
    
    if time.time() - START_TIME >= MAX_RUNTIME:
        break

elapsed = time.time() - START_TIME
print(f"\n{'='*60}")
print(f"DONE: {total_uploaded} uploaded, {total_failed} failed")
print(f"Runtime: {elapsed/3600:.1f}h")

with open("upload_progress.json", "w") as f:
    json.dump({
        "uploaded": total_uploaded,
        "skipped": 0,
        "failed": total_failed,
        "runtime_hours": elapsed / 3600,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }, f, indent=2)
