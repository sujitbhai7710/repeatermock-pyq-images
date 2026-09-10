#!/usr/bin/env python3
"""Upload PYQ images from source repo to this repo via GitHub API."""
import json, os, time, base64, urllib.request, urllib.parse, httpx, sys
from datetime import datetime, timezone

SOURCE_REPO = "sujitbhai7710/repeatermock-mass-scraper"
TARGET_REPO = os.environ.get("GITHUB_REPOSITORY", "sujitbhai7710/repeatermock-pyq-images")
GH_TOKEN = os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
SOURCE_TOKEN = os.environ.get("SOURCE_TOKEN", GH_TOKEN)

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
MAX_RUNTIME = 5.4 * 3600  # 5.4 hours (safety margin)

def list_images(series_folder):
    all_images = []
    path = f"scraped_output/{series_folder}/images"
    for page in range(1, 200):
        encoded = urllib.parse.quote(path)
        url = f"https://api.github.com/repos/{SOURCE_REPO}/contents/{encoded}?per_page=100&page={page}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"token {SOURCE_TOKEN}",
            "Accept": "application/vnd.github+json",
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                items = json.loads(r.read().decode())
        except:
            break
        if not isinstance(items, list) or len(items) == 0:
            break
        for item in items:
            if item['type'] == 'file' and item['name'].endswith('.png'):
                all_images.append(item['name'])
        if len(items) < 100:
            break
    return all_images

def check_exists(series_target, image_name):
    path = f"{series_target}/images/{image_name}"
    encoded = urllib.parse.quote(path)
    url = f"https://api.github.com/repos/{TARGET_REPO}/contents/{encoded}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
    })
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return True
    except:
        return False

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

# Main
print(f"Target: {TARGET_REPO}")
print(f"Max runtime: 5.4 hours")

total_uploaded = 0
total_skipped = 0
total_failed = 0

for si, (series_folder, series_target) in enumerate(SERIES_MAP):
    elapsed = time.time() - START_TIME
    if elapsed >= MAX_RUNTIME:
        print(f"\n⏰ Max runtime reached - stopping")
        break
    
    print(f"\n--- {si+1}/{len(SERIES_MAP)}: {series_target}/images/ ---")
    
    # List images
    print(f"  Listing...", end=" ", flush=True)
    all_images = list_images(series_folder)
    print(f"{len(all_images)} images found")
    
    # Upload
    for img in all_images:
        elapsed = time.time() - START_TIME
        if elapsed >= MAX_RUNTIME:
            print(f"\n⏰ Time limit reached")
            break
        
        if check_exists(series_target, img):
            total_skipped += 1
            continue
        
        content = download_image(series_folder, img)
        if not content:
            total_failed += 1
            continue
        
        if upload_image(series_target, img, content):
            total_uploaded += 1
        else:
            total_failed += 1
        
        if (total_uploaded + total_failed) % 50 == 0:
            print(f"  📤 {total_uploaded} uploaded, {total_skipped} skipped, {total_failed} failed", flush=True)
        
        time.sleep(0.3)

elapsed = time.time() - START_TIME
print(f"\n{'='*60}")
print(f"DONE: {total_uploaded} uploaded, {total_skipped} skipped, {total_failed} failed")
print(f"Runtime: {elapsed/3600:.1f}h")

# Save progress
with open("upload_progress.json", "w") as f:
    json.dump({
        "uploaded": total_uploaded,
        "skipped": total_skipped,
        "failed": total_failed,
        "runtime_hours": elapsed / 3600,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }, f, indent=2)
