"""Crawl toàn bộ comment của 1 thread voz.vn.

Usage:
    python voz_crawl.py <thread_url> <out_dir> [--delay 1.0]

Input có thể là link bất kỳ page nào của thread (page-3, #post-..., ...).
Output: <out_dir>/<slug-thread>.json (tự tạo out_dir nếu chưa có)
"""
import argparse
import json
import os
import re
import sys
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://voz.vn"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "vi,en;q=0.9",
}


def thread_base(url: str) -> str:
    m = re.search(r"voz\.vn/t/([^/?#]+)", url)
    if not m:
        sys.exit(f"Link không phải thread voz: {url}")
    return f"{BASE}/t/{m.group(1)}/"


def fetch(session: requests.Session, url: str, retries: int = 4) -> str:
    for i in range(retries):
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 200:
                return r.text
            if r.status_code not in (429, 500, 502, 503, 504):
                r.raise_for_status()
        except requests.RequestException as e:
            if i == retries - 1:
                raise
            print(f"  lỗi {e}, thử lại...", file=sys.stderr)
        time.sleep(2 ** (i + 1))
    raise RuntimeError(f"Không tải được {url}")


def last_page(soup: BeautifulSoup) -> int:
    pages = [int(a.get_text(strip=True)) for a in soup.select(".pageNav-page a")
             if a.get_text(strip=True).isdigit()]
    return max(pages, default=1)


# Dòng chữ ký app: "via theNEXTvoz for iPhone", "Sent from ... using vozFApp", "Gửi từ ... bằng vozFApp"
SIGNATURE_RE = re.compile(r"^\s*(via theNEXTvoz\b.*|.*\bvozFApp\s*)$", re.I | re.M)


def absolute(url: str) -> str:
    return urljoin(BASE, url) if url else ""


def clean_text(node, attachments: list[str] = ()) -> str:
    """Lấy text của comment, chèn URL ảnh/link vào đúng vị trí."""
    for tag in node.find_all("noscript"):  # bản sao ảnh cho trình duyệt tắt JS
        tag.decompose()
    for br in node.find_all("br"):
        br.replace_with("\n")
    for img in node.select("img.smilie"):  # emoji -> ký tự / shortname
        img.replace_with(img.get("alt") or "")
    # Khung xem trước link (Google Maps, báo...) -> "tiêu đề (url)"
    for box in node.select(".bbCodeBlock--unfurl"):
        title = box.select_one(".js-unfurl-title")
        title = title.get_text(" ", strip=True) if title else ""
        url = box.get("data-url") or ""
        box.replace_with(f"\n{title} ({url})\n" if title else f"\n{url}\n")
    # Ảnh chèn trong bài
    for wrap in node.select(".bbImageWrapper"):
        img = wrap.select_one("img")
        url = wrap.get("data-src") or (img and (img.get("data-src") or img.get("src")))
        wrap.replace_with(f"\n[ảnh: {absolute(url)}]\n")
    for img in node.select("img.bbImage"):
        img.replace_with(f"\n[ảnh: {absolute(img.get('data-src') or img.get('src'))}]\n")
    # Video nhúng
    for iframe in node.select("iframe[src]"):
        iframe.replace_with(f"\n[video: {absolute(iframe['src'])}]\n")
    # Link: giữ chữ, thêm URL nếu chữ không phải là URL
    for a in node.select("a[href]"):
        if "username" in (a.get("class") or []):  # @mention
            continue
        href = absolute(a["href"])
        text = a.get_text(strip=True)
        if not text or text.startswith(("http", "www.")):
            a.replace_with(href)
        else:
            a.replace_with(text if a["href"] in text or href in text else f"{text} ({href})")

    text = node.get_text()
    if attachments:
        text += "\n" + "\n".join(f"[ảnh: {u}]" for u in attachments)
    text = SIGNATURE_RE.sub("", text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def parse_posts(html: str, page: int) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for art in soup.select("article.message--post"):
        post_id = art.get("data-content", "").replace("post-", "")
        body = art.select_one(".message-body .bbWrapper") or art.select_one(".bbWrapper")
        if body is None:
            continue

        # Các comment được quote/reply (chỉ quote cấp ngoài cùng)
        replies_to = []
        for bq in body.find_all("blockquote", class_="bbCodeBlock--quote", recursive=False):
            src = re.search(r"post:\s*(\d+)", bq.get("data-source", ""))
            replies_to.append({
                "post_id": src.group(1) if src else None,
                "user": bq.get("data-quote"),
            })
            bq.decompose()
        # Bỏ spoiler/quote lồng sót lại? giữ spoiler, chỉ bỏ quote
        for bq in body.select("blockquote.bbCodeBlock--quote"):
            bq.decompose()

        # Tệp đính kèm nằm ngoài bbWrapper
        attachments = [absolute(a["href"]) for a in art.select(".message-attachments a.file-preview[href]")]

        t = art.select_one("time.u-dt")
        floor = None
        opp = art.select_one(".message-attribution-opposite")
        if opp:
            m = re.search(r"#\s*([\d.,]+)", opp.get_text())
            if m:
                floor = int(re.sub(r"\D", "", m.group(1)))

        out.append({
            "post_id": post_id,
            "floor": floor,
            "page": page,
            "user": art.get("data-author"),
            "time": t.get("datetime") if t else None,
            "content": clean_text(body, attachments),
            "reply_to_post_ids": [r["post_id"] for r in replies_to if r["post_id"]],
            "reply_to_users": [r["user"] for r in replies_to if r["user"]],
            "is_relevant": None,  # True/False, điền sau khi phân loại
        })
    return out


def crawl(url: str, delay: float = 1.0) -> dict:
    base = thread_base(url)
    s = requests.Session()
    s.headers.update(HEADERS)

    html = fetch(s, base)
    soup = BeautifulSoup(html, "lxml")
    title = soup.select_one("h1.p-title-value")
    if title:
        for lbl in title.select(".label, .label-append"):
            lbl.decompose()
    title = title.get_text(strip=True) if title else ""
    n = last_page(soup)
    print(f"{title} — {n} page", file=sys.stderr)

    posts = parse_posts(html, 1)
    print(f"  page 1/{n}: {len(posts)} posts", file=sys.stderr)
    for p in range(2, n + 1):
        time.sleep(delay)
        items = parse_posts(fetch(s, f"{base}page-{p}"), p)
        posts.extend(items)
        print(f"  page {p}/{n}: {len(items)} posts", file=sys.stderr)

    # Dedupe (phòng trường hợp thread có bài mới chen trong lúc crawl)
    seen, uniq = set(), []
    for x in posts:
        if x["post_id"] not in seen:
            seen.add(x["post_id"])
            uniq.append(x)
    return {"url": base, "title": title, "pages": n, "total": len(uniq), "posts": uniq}


def save(data: dict, basename: str) -> None:
    with open(f"{basename}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("out_dir", help="thư mục lưu file JSON")
    ap.add_argument("--delay", type=float, default=1.0, help="giây nghỉ giữa các page")
    a = ap.parse_args()

    data = crawl(a.url, a.delay)
    slug = re.sub(r"[^\w.-]", "_", thread_base(a.url).rstrip("/").split("/")[-1])
    os.makedirs(a.out_dir, exist_ok=True)
    out = os.path.join(a.out_dir, slug)

    # Crawl lại thread đã có: giữ nhãn is_relevant cũ theo post_id
    if os.path.exists(f"{out}.json"):
        with open(f"{out}.json", encoding="utf-8") as f:
            old = {p["post_id"]: p.get("is_relevant") for p in json.load(f)["posts"]}
        for p in data["posts"]:
            p["is_relevant"] = old.get(p["post_id"])
        kept = sum(p["post_id"] in old for p in data["posts"])
        print(f"  giữ nhãn cũ cho {kept}/{data['total']} comment", file=sys.stderr)

    save(data, out)
    print(f"Xong: {data['total']} comment -> {out}.json", file=sys.stderr)


if __name__ == "__main__":
    main()
