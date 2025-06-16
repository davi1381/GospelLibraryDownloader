import argparse
import base64
import json
import os
import re
import urllib.request
import zlib
from tqdm import tqdm

BASE_URL = "https://www.churchofjesuschrist.org"
VOLUMES = {
    "Volume 1": "saints-v1",
    # "Volume 2": "saints-v2",
    # "Volume 3": "saints-v3",
    # "Volume 4": "saints-v4",
}

HEADERS = {
    "User-Agent": "SaintsDownloader",
    "Accept-Encoding": "gzip, deflate, br",
}


def get_html(url):
    req = urllib.request.Request(url)
    for k, v in HEADERS.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
        try:
            data = zlib.decompress(data, 16 + zlib.MAX_WBITS)
        except zlib.error:
            pass
        return data.decode("utf-8")


def extract_chapter_links(volume_slug):
    html = get_html(f"{BASE_URL}/study/history/{volume_slug}?lang=eng")
    links = re.findall(r'href="(/study/history/{}/[^\" ]*)"'.format(volume_slug), html)
    chapters = [link for link in links if re.search(r'/\d{2}-', link)]
    return list(dict.fromkeys(chapters))


def parse_audio_link(chapter_url):
    html = get_html(f"{BASE_URL}{chapter_url}")
    m = re.search(r'window.__INITIAL_STATE__="([^"]+)"', html)
    if not m:
        return None, None
    decoded = base64.b64decode(m.group(1))
    data = json.loads(decoded)
    store = data.get("reader", {}).get("contentStore", {})
    entry = store.get(chapter_url.replace("/study", ""))
    if not entry:
        # content key may omit '/study'
        entry = store.get(chapter_url.split("?", 1)[0].replace("/study", ""))
    if not entry:
        return None, None
    title = entry.get("meta", {}).get("title", "chapter")
    audio_list = entry.get("meta", {}).get("audio", [])
    audio_url = None
    for a in audio_list:
        if a.get("variant") == "male":
            audio_url = a.get("mediaUrl")
            break
    if not audio_url and audio_list:
        audio_url = audio_list[0].get("mediaUrl")
    return audio_url, title


def download_file(url, path):
    if not url:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        return
    req = urllib.request.Request(url)
    for k, v in HEADERS.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
        with open(path, "wb") as f:
            f.write(data)


def process_volume(name, slug, dest):
    chapter_links = extract_chapter_links(slug)
    vol_dir = os.path.join(dest, name)
    with tqdm(total=len(chapter_links)) as bar:
        for link in chapter_links:
            audio_url, title = parse_audio_link(link)
            num = re.search(r'/([0-9][0-9])-', link)
            prefix = num.group(1) if num else ""
            filename = f"{prefix} {title}.mp3".replace('/', '-')
            out_path = os.path.join(vol_dir, filename)
            download_file(audio_url, out_path)
            bar.update(1)


def main():
    parser = argparse.ArgumentParser(description="Download Saints audio chapters")
    parser.add_argument("-dest", default="./saints_audio", help="Output directory")
    args = parser.parse_args()

    for name, slug in VOLUMES.items():
        process_volume(name, slug, args.dest)


if __name__ == "__main__":
    main()
