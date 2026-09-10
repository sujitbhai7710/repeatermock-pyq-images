#!/usr/bin/env python3
"""Upload PYQ images from source repo to this repo via GitHub API."""
import json, os, time, base64, urllib.request, urllib.parse, httpx
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

def get_all_source_files():
    """Get ALL files from source repo using git trees API (one call, recursive)."""
    url = f"https://api.github.com/repos/{SOURCE_REPO}/git/trees/main?recursive=1"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "Mozilla/5.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        return data.get('tree', [])
    except Exception as e:
        print(f"  Error fetching tree: {e}")
        return []

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

# Get all source files in one API call
print("Fetching source repo file tree...", flush=True)
tree = get_all_source_files()
print(f"Total files in source repo: {len(tree)}")

# Filter to only image files in the 7 series folders
all_images_by_series = {}
for item in tree:
    if item.get('type') != 'blob':
        continue
    path = item['path']
    if not path.endswith('.png'):
        continue
    
    for series_folder, series_target in SERIES_MAP:
        prefix = f"scraped_output/{series_folder}/images/"
        if path.startswith(prefix):
            image_name = path[len(prefix):]
            if '/' not in image_name:  # Direct file, not in subfolder
                all_images_by_series.setdefault((series_folder, series_target), []).append(image_name)
            break

print(f"\nImages found per series:")
for (sf, st), images in all_images_by_series.items():
    print(f"  {st}: {len(images)} images")

total_uploaded = 0
total_skipped = 0
total_failed = 0

for (series_folder, series_target), images in all_images_by_series.items():
    elapsed = time.time() - START_TIME
    if elapsed >= MAX_RUNTIME:
        print(f"\n⏰ Max runtime reached - stopping")
        break
    
    print(f"\n--- {series_target}/images/ ({len(images)} images) ---")
    
    for img in images:
        elapsed = time.time() - START_TIME
        if elapsed >= MAX_RUNTIME:
            print(f"\n⏰ Time limit reached")
            break
        
        # Check if already exists (only check every 10th image to save time)
        if total_uploaded % 10 == 0 and check_exists(series_target, img):
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

with open("upload_progress.json", "w") as f:
    json.dump({
        "uploaded": total_uploaded,
        "skipped": total_skipped,
        "failed": total_failed,
        "runtime_hours": elapsed / 3600,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }, f, indent=2)
