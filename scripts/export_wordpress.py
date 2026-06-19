import json
import re
import html
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


BASE_URL = "https://transferwiedzy.uew.pl"
OUTPUT_DIR = Path("public")
JSON_OUTPUT = OUTPUT_DIR / "site-export.json"
MD_OUTPUT = OUTPUT_DIR / "site-export.md"


ENDPOINTS = {
    "pages": f"{BASE_URL}/wp-json/wp/v2/pages?per_page=100&_fields=id,date,modified,slug,link,title,content",
    "posts": f"{BASE_URL}/wp-json/wp/v2/posts?per_page=100&_fields=id,date,modified,slug,link,title,content",
    "media": f"{BASE_URL}/wp-json/wp/v2/media?per_page=100&_fields=id,date,modified,slug,source_url,alt_text,caption,title,mime_type",
}


def fetch_json(url: str):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "transferwiedzy-export-bot/1.0"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset))


def strip_html(raw_html: str) -> str:
    if not raw_html:
        return ""

    text = re.sub(r"<script[^>]*>.*?</script>", " ", raw_html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)

    text = re.sub(r"</(p|div|h1|h2|h3|h4|h5|h6|li|br)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)

    text = html.unescape(text)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def get_rendered(value):
    if isinstance(value, dict):
        return value.get("rendered", "")
    return value or ""


def normalize_content_item(item: dict, item_type: str) -> dict:
    title_html = get_rendered(item.get("title"))
    content_html = get_rendered(item.get("content"))

    title_text = strip_html(title_html)
    content_text = strip_html(content_html)

    return {
        "id": item.get("id"),
        "type": item_type,
        "title": title_text,
        "slug": item.get("slug"),
        "url": item.get("link"),
        "date": item.get("date"),
        "modified": item.get("modified"),
        "content_html": content_html,
        "content_text": content_text,
        "source": BASE_URL,
    }


def normalize_media_item(item: dict) -> dict:
    title_html = get_rendered(item.get("title"))
    caption_html = get_rendered(item.get("caption"))

    return {
        "id": item.get("id"),
        "type": "media",
        "title": strip_html(title_html),
        "slug": item.get("slug"),
        "url": item.get("source_url"),
        "date": item.get("date"),
        "modified": item.get("modified"),
        "mime_type": item.get("mime_type"),
        "alt_text": item.get("alt_text") or "",
        "caption_text": strip_html(caption_html),
        "source": BASE_URL,
    }


def build_markdown(export_data: dict) -> str:
    lines = []
    lines.append("# Eksport treści Transfer Wiedzy UEW")
    lines.append("")
    lines.append(f"Data eksportu: {export_data['exported_at']}")
    lines.append(f"Źródło: {export_data['source']}")
    lines.append("")

    lines.append("## Strony i wpisy")
    lines.append("")

    for item in export_data["content_items"]:
        lines.append(f"### {item.get('title') or 'Bez tytułu'}")
        lines.append("")
        lines.append(f"- Typ: {item.get('type')}")
        lines.append(f"- URL: {item.get('url')}")
        lines.append(f"- Ostatnia modyfikacja: {item.get('modified')}")
        lines.append("")
        lines.append(item.get("content_text") or "")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## Media i dokumenty")
    lines.append("")

    for media in export_data["media_items"]:
        lines.append(f"### {media.get('title') or 'Bez tytułu'}")
        lines.append("")
        lines.append(f"- URL: {media.get('url')}")
        lines.append(f"- Typ pliku: {media.get('mime_type')}")
        lines.append(f"- Ostatnia modyfikacja: {media.get('modified')}")
        if media.get("caption_text"):
            lines.append(f"- Podpis: {media.get('caption_text')}")
        lines.append("")

    return "\n".join(lines)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pages = fetch_json(ENDPOINTS["pages"])
    posts = fetch_json(ENDPOINTS["posts"])
    media = fetch_json(ENDPOINTS["media"])

    content_items = []
    content_items.extend(normalize_content_item(item, "page") for item in pages)
    content_items.extend(normalize_content_item(item, "post") for item in posts)

    media_items = [normalize_media_item(item) for item in media]

    export_data = {
        "source": BASE_URL,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "pages_count": len(pages),
            "posts_count": len(posts),
            "media_count": len(media),
            "content_items_count": len(content_items),
        },
        "content_items": content_items,
        "media_items": media_items,
    }

    JSON_OUTPUT.write_text(
        json.dumps(export_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    MD_OUTPUT.write_text(
        build_markdown(export_data),
        encoding="utf-8"
    )

    print("Eksport zakończony.")
    print(f"Strony: {len(pages)}")
    print(f"Wpisy: {len(posts)}")
    print(f"Media: {len(media)}")
    print(f"Plik JSON: {JSON_OUTPUT}")
    print(f"Plik Markdown: {MD_OUTPUT}")


if __name__ == "__main__":
    main()
