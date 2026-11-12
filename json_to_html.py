"""Gộp các file JSON (output của voz_crawl.py) thành 1 file HTML dạng chat nhóm.

Chỉ lấy comment có is_relevant = True (dùng --all để lấy hết).

Usage:
    python json_to_html.py "nhatrang/*.json" [-o site/nhatrang.html] [--title "..."] [--all]

Mặc định ghi ra site/<tên thư mục chứa JSON>.html (thư mục site/ được deploy lên GitHub Pages).
"""
import argparse
import glob
import html
import json
import os
import re
import zlib

SITE_DIR = "site"  # thư mục deploy lên GitHub Pages
URL_RE = re.compile(r"https?://[^\s<>\"]+")
SNIPPET_LEN = 140


MEDIA_RE = re.compile(r"\[(ảnh|video): (https?://[^\]\s]+)\]")


def fmt_time(iso: str | None) -> str:
    """2025-09-03T16:20:17+0700 -> 3/9/25 16:20"""
    m = re.match(r"(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d)", iso or "")
    if not m:
        return ""
    y, mo, d, h, mi = m.groups()
    return f"{int(d)}/{int(mo)}/{y[2:]} {h}:{mi}"


def esc_text(s: str) -> str:
    """[ảnh: url] -> link gọn, rồi escape + linkify phần còn lại."""
    out, last = [], 0
    for m in MEDIA_RE.finditer(s):
        out.append(esc_plain(s[last:m.start()]))
        icon = "🖼 ảnh" if m.group(1) == "ảnh" else "▶ video"
        out.append(f'<a class="media" href="{html.escape(m.group(2))}" target="_blank" rel="noopener">{icon}</a>')
        last = m.end()
    out.append(esc_plain(s[last:]))
    return "".join(out)


def esc_plain(s: str) -> str:
    """Escape + linkify URL + giữ xuống dòng."""
    out, last = [], 0
    for m in URL_RE.finditer(s):
        out.append(html.escape(s[last:m.start()]))
        url = m.group(0).rstrip(").,")
        short = re.sub(r"^https?://(www\.)?", "", url)
        short = short[:40] + "…" if len(short) > 40 else short
        out.append(f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(short)}</a>')
        last = m.start() + len(url)
    out.append(html.escape(s[last:]))
    return "".join(out).replace("\n", "<br>")


def snippet(s: str) -> str:
    s = MEDIA_RE.sub(lambda m: f"[{m.group(1)}]", s)
    s = re.sub(r"\s+", " ", URL_RE.sub("[link]", s)).strip()
    return s[:SNIPPET_LEN] + "…" if len(s) > SNIPPET_LEN else s


def hue(name: str) -> int:
    return zlib.crc32(name.encode("utf-8")) % 360


def render_thread(idx: int, d: dict, show_all: bool) -> tuple[str, int]:
    posts = d["posts"]
    by_id = {p["post_id"]: p for p in posts}
    keep = [p for p in posts if show_all or p.get("is_relevant") is True]
    if not keep:
        return "", 0
    op = posts[0]["user"] if posts else None
    sid = f"t{idx}"

    msgs, prev_user = [], None
    for p in keep:
        user = p["user"] or "?"
        first = user != prev_user
        prev_user = user

        replies = []
        ids = p.get("reply_to_post_ids") or []
        users = p.get("reply_to_users") or []
        for i, rid in enumerate(ids):
            src = by_id.get(rid)
            ruser = src["user"] if src else (users[i] if i < len(users) else "?")
            text = snippet(src["content"]) if src else ""
            target = (show_all or src.get("is_relevant") is True) if src else False
            tag = "a" if target else "div"
            href = f' href="#{sid}-{rid}"' if target else ""
            replies.append(
                f'<{tag} class="quote"{href}><b>↩ {html.escape(ruser)}</b>'
                f'{"<span>" + html.escape(text) + "</span>" if text else ""}</{tag}>'
            )
        if not ids and users:  # quote không có post_id
            replies = [f'<div class="quote"><b>↩ {html.escape(u)}</b></div>' for u in users]

        is_op = user == op
        avatar = (f'<div class="av" style="--h:{hue(user)}">{html.escape(user[:1].upper())}</div>'
                  if first else '<div class="av ghost"></div>')
        when = fmt_time(p.get("time"))
        name = (f'<div class="name"><b style="--h:{hue(user)}">{html.escape(user)}</b>'
                f'{"<em>chủ thớt</em>" if is_op else ""}<time>{when}</time></div>') if first else ""
        stamp = "" if first else f'<time class="stamp">{when}</time>'
        msgs.append(
            f'<div class="msg{" first" if first else ""}{" op" if is_op else ""}" id="{sid}-{p["post_id"]}">'
            f'{avatar}<div class="col">{name}<div class="bubble">{"".join(replies)}'
            f'<div class="txt">{esc_text(p["content"])}</div>{stamp}</div></div></div>'
        )

    head = (f'<header class="th"><h2>{html.escape(d["title"])}</h2>'
            f'<p>{len(keep)}/{len(posts)} comment · {d.get("pages", "?")} page · '
            f'<a href="{html.escape(d["url"])}" target="_blank" rel="noopener">mở trên voz</a></p></header>')
    return f'<section id="{sid}">{head}<div class="chat">{"".join(msgs)}</div></section>', len(keep)


CSS = """
:root{--bg:#f4f5f7;--card:#fff;--fg:#1c1e21;--mut:#65676b;--bub:#eceef1;--op:#dbe9ff;--q:#0000000d;--line:#e3e5e8;--acc:#0a66e0}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#111214;--card:#1b1c1f;--fg:#e4e6eb;--mut:#a0a4ab;--bub:#2a2c30;--op:#1d3557;--q:#ffffff12;--line:#2e3035;--acc:#5aa2ff}}
:root[data-theme=dark]{--bg:#111214;--card:#1b1c1f;--fg:#e4e6eb;--mut:#a0a4ab;--bub:#2a2c30;--op:#1d3557;--q:#ffffff12;--line:#2e3035;--acc:#5aa2ff}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]) .name b{color:hsl(var(--h) 60% 65%)}}
:root[data-theme=dark] .name b{color:hsl(var(--h) 60% 65%)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--acc)}
.wrap{max-width:760px;margin:0 auto;padding:24px 16px 80px}
h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--mut);margin:0 0 16px;font-size:14px}
nav{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:8px 0;margin-bottom:28px}
nav a{display:flex;justify-content:space-between;gap:12px;padding:6px 16px;text-decoration:none;color:var(--fg)}
nav a:hover{background:var(--q)}
nav span{color:var(--mut);font-size:13px;white-space:nowrap}
section{background:var(--card);border:1px solid var(--line);border-radius:14px;margin-bottom:28px;overflow:hidden}
.th{position:sticky;top:0;z-index:2;background:var(--card);border-bottom:1px solid var(--line);padding:12px 16px}
.th h2{font-size:17px;margin:0}
.th p{margin:2px 0 0;color:var(--mut);font-size:13px}
.chat{padding:12px 12px 16px}
.msg{display:flex;gap:8px;margin-top:3px;scroll-margin-top:90px}
.msg.first{margin-top:14px}
.av{flex:0 0 32px;height:32px;border-radius:50%;display:grid;place-items:center;font-weight:600;font-size:14px;color:#fff;background:hsl(var(--h) 55% 48%);margin-top:20px}
.av.ghost{visibility:hidden;height:0;margin:0}
.col{min-width:0;max-width:calc(100% - 40px)}
.name{font-size:12.5px;margin:0 0 2px 10px;display:flex;flex-wrap:wrap;align-items:baseline;gap:0 6px}
.name b{font-weight:600;color:hsl(var(--h) 50% 45%)}
.name em{font-style:normal;color:var(--mut)}
.name time{color:var(--mut);font-size:11.5px}
.stamp{display:block;text-align:right;color:var(--mut);font-size:11px;margin-top:2px}
a.media{display:inline-block;font-size:13px;padding:1px 8px;margin:2px 0;border-radius:10px;background:var(--q);text-decoration:none}
.bubble{background:var(--bub);border-radius:16px;padding:8px 12px;overflow-wrap:anywhere}
.op .bubble{background:var(--op)}
.quote{display:block;border-left:3px solid var(--mut);background:var(--q);border-radius:6px;padding:4px 8px;margin:2px 0 6px;font-size:13px;color:var(--mut);text-decoration:none}
.quote b{color:var(--fg);font-weight:600;margin-right:6px}
a.quote:hover{border-left-color:var(--acc)}
.msg:target .bubble{outline:2px solid var(--acc)}
.top{position:fixed;right:16px;bottom:16px;width:40px;height:40px;border-radius:50%;display:grid;place-items:center;background:var(--card);border:1px solid var(--line);text-decoration:none;color:var(--fg);box-shadow:0 2px 8px #0002}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", help="file JSON (hỗ trợ glob)")
    ap.add_argument("-o", "--out", help="mặc định: site/<tên thư mục chứa JSON>.html")
    ap.add_argument("--title", default="Tổng hợp comment voz")
    ap.add_argument("--all", action="store_true", help="lấy cả comment không relevant")
    a = ap.parse_args()

    files = sorted({f for pat in a.inputs for f in (glob.glob(pat) or [pat])})
    sections, toc, total = [], [], 0
    for i, f in enumerate(files):
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        sec, n = render_thread(i, d, a.all)
        if not n:
            continue
        sections.append(sec)
        toc.append(f'<a href="#t{i}">{html.escape(d["title"])}<span>{n} tin</span></a>')
        total += n

    page = (
        '<!doctype html><html lang="vi"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(a.title)}</title><style>{CSS}</style></head>"
        f'<body><div class="wrap" id="top"><h1>{html.escape(a.title)}</h1>'
        f'<p class="sub">{len(sections)} bài · {total} comment</p>'
        f'<nav>{"".join(toc)}</nav>{"".join(sections)}</div>'
        '<a class="top" href="#top" aria-label="Lên đầu trang">↑</a></body></html>'
    )
    if not a.out:
        folder = os.path.basename(os.path.dirname(os.path.abspath(files[0])))
        a.out = os.path.join(SITE_DIR, f"{folder}.html")
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"Xong: {len(sections)} bài, {total} comment -> {a.out}")


if __name__ == "__main__":
    main()
