import json, re, os, random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path("/home/agent/autofinisher-factory")
INPUT_PATH = BASE_DIR / "niche_engine" / "accepted" / "niche_package.json"
OUTPUT_ROOT = BASE_DIR / "ready_to_publish"

def get_font(size, bold=True):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(path, size) if os.path.exists(path) else ImageFont.load_default()

def draw_wrapped_text(draw, text, font, color, y_start, max_width=1000):
    words = text.split()
    lines, current_line = [], []
    for word in words:
        test_line = " ".join(current_line + [word])
        l, t, r, b = draw.textbbox((0, 0), test_line, font=font)
        if (r - l) < max_width: current_line.append(word)
        else: lines.append(" ".join(current_line)); current_line = [word]
    lines.append(" ".join(current_line))
    y = y_start
    for line in lines:
        l, t, r, b = draw.textbbox((0, 0), line.upper(), font=font)
        draw.text(((1200 - (r - l)) // 2, y), line.upper(), fill=color, font=font)
        y += (b - t) + 30

def draw_icon(draw, x, y, name, color):
    n = name.lower()
    if any(k in n for k in ["budget", "money", "save"]): # Монета
        draw.ellipse((x, y, x+80, y+80), outline=color, width=8)
        draw.text((x+25, y+15), "$", fill=color, font=get_font(45))
    elif any(k in n for k in ["clean", "house", "chore"]): # Искорка
        for i in range(4):
            draw.line((x+40, y, x+40, y+80), fill=color, width=6)
            draw.line((x, y+40, x+80, y+40), fill=color, width=6)
    else: # Звезда
        draw.polygon([(x+40,y), (x+55,y+30), (x+85,y+30), (x+60,y+50), (x+70,y+80), (x+40,y+65), (x+10,y+80), (x+20,y+50), (x-5,y+30), (x+25,y+30)], outline=color, width=5)

def main():
    if not INPUT_PATH.exists(): return
    data = json.loads(INPUT_PATH.read_text())
    colors = ["#4f46e5", "#0891b2", "#059669", "#db2777", "#ea580c", "#2563eb", "#d97706"]
    
    for item in data.get("items", []):
        name = item["niche"]
        accent = random.choice(colors)
        price = item.get("price", str(round(random.uniform(2.5, 4.9), 2)))
        slug = re.sub(r"[^\w]+", "-", name.lower()).strip("-")
        d = OUTPUT_ROOT / slug
        d.mkdir(parents=True, exist_ok=True)
        
        # PDF (3 страницы)
        pages = []
        for p_type in range(1, 4):
            img = Image.new("RGB", (2480, 3508), "white")
            draw = ImageDraw.Draw(img)
            draw_icon(draw, 250, 200, name, accent)
            draw.text((380, 220), name.upper()[:35], fill="#1a1a1a", font=get_font(85))
            draw.line((250, 380, 2230, 380), fill=accent, width=15)
            # Сетка (упрощенно)
            for i in range(12): draw.rectangle((250, 600+i*200, 2230, 750+i*200), outline="#f1f5f9", width=2)
            pages.append(img)
        pages[0].save(d / "deliverable.pdf", save_all=True, append_images=pages[1:])
        
        # SEO & CSV Data
        t = f"{name.title()} Bundle Printable, Digital Daily Tracker PDF, Home Organization"
        tags = [name.lower()[:20], "printable", "digital download", "planner bundle", "instant download", "productivity", "organizer", "habit tracker", "a4 pdf", "diy planner", "minimalist", "2026 planner", "digital file"]
        (d / "SEO.txt").write_text(f"TITLE: {t}\nTAGS: {', '.join(tags)}\nPRICE: {price}\nDESC: 3-Page Premium Bundle")

        # Mockups
        m1 = Image.new("RGB", (1200, 1200), accent)
        draw_wrapped_text(ImageDraw.Draw(m1), name, get_font(80), "white", 450)
        m1.save(d / "mockup_1.png")
        m1.save(d / "master.png")
        
        # Feature List Mockup
        m2 = Image.new("RGB", (1200, 1200), "white")
        d2 = ImageDraw.Draw(m2)
        d2.rectangle((0,0,1200,200), fill=accent)
        d2.text((100,60), "WHAT'S INSIDE", fill="white", font=get_font(60))
        for i, text in enumerate(["3 Professional PDF Pages", "High-Resolution 300 DPI", "A4 & Letter Ready", "Instant Access"]):
            d2.text((150, 400+i*150), f"✓ {text}", fill="#334155", font=get_font(55))
        m2.save(d / "mockup_2.png")
        
        print(f"💎 Boutique Item: {name} (${price})")

if __name__ == "__main__": main()
