import os, re, csv
from pathlib import Path

BASE_DIR = Path("/home/agent/autofinisher-factory/ready_to_publish")
OUTPUT_HTML = BASE_DIR / "index.html"
OUTPUT_CSV = BASE_DIR / "etsy_mass_import.csv"

HTML_HEAD = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>SGR Terminal: SignalReview</title>
<style>
    body { font-family: 'JetBrains Mono', monospace; background: #0a0a0c; color: #00ff41; padding: 40px; line-height: 1.6; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 30px; }
    .card { border: 1px solid #00ff41; padding: 20px; background: #111; box-shadow: 0 0 15px rgba(0, 255, 65, 0.1); }
    .thumb { width: 100%; height: 250px; object-fit: cover; border-bottom: 1px solid #00ff41; margin-bottom: 15px; }
    .price { color: #fff; background: #00ff41; color: #000; padding: 2px 8px; font-weight: bold; }
    .btn { display: block; border: 1px solid #00ff41; color: #00ff41; text-align: center; padding: 10px; margin-top: 10px; text-decoration: none; text-transform: uppercase; font-size: 12px; }
    .btn:hover { background: #00ff41; color: #000; }
</style></head><body>
<h1>[SGR_ORCHESTRATOR_V2] :: STATUS_ONLINE</h1>
<div class="grid">
"""

def main():
    folders = [d for d in sorted(BASE_DIR.iterdir()) if d.is_dir()]
    html = HTML_HEAD
    
    csv_data = [['Title', 'Description', 'Price', 'Tags', 'Image URL']]
    
    for d in folders:
        seo_path = d / "SEO.txt"
        if not seo_path.exists(): continue
        
        raw = seo_path.read_text()
        # Безопасный поиск через regex
        title = (re.search(r"TITLE:\s*(.*)", raw) or re.search(r"^(.*)", raw)).group(1).strip()
        price = (re.search(r"PRICE:\s*\$(.*)", raw) or re.search(r"PRICE:\s*(.*)", raw) or re.compile(r"3.50")).group(1).strip()
        tags = (re.search(r"TAGS:\s*(.*)", raw) or re.compile(r"")).group(1).strip()
        
        img_src = f"{d.name}/mockup_1.png" if (d / "mockup_1.png").exists() else f"{d.name}/master.png"
        
        html += f"""<div class="card">
            <img src="{img_src}" class="thumb">
            <div><span class="price">${price}</span></div>
            <div style="margin: 10px 0; font-weight: bold;">{title[:70]}...</div>
            <a href="{d.name}/deliverable.pdf" class="btn" download>Download Bundle</a>
            <button class="btn" style="width:100%; cursor:pointer;" onclick="navigator.clipboard.writeText('{title}')">Copy Title</button>
            <button class="btn" style="width:100%; cursor:pointer;" onclick="navigator.clipboard.writeText('{tags}')">Copy 13 Tags</button>
        </div>"""
        csv_data.append([title, "Premium bundle", price, tags, img_src])

    html += "</div></body></html>"
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    
    with open(OUTPUT_CSV, 'w', newline='') as f:
        writer = csv.writer(f); writer.writerows(csv_data)
        
    print(f"✅ SGR Factory synced. {len(folders)} items ready at signalreview.co/index.html")

if __name__ == "__main__": main()
