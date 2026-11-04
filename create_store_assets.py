#!/usr/bin/env python3
"""Generate Chrome Web Store assets for Traba-Hero."""
from PIL import Image, ImageDraw, ImageFont
import os

OUT_DIR = r"E:\traba-hero\store_assets"
os.makedirs(OUT_DIR, exist_ok=True)

# Colors from DESIGN.md
PRIMARY = "#003c90"      # Sapphire Blue
ACCENT = "#7c5800"       # Gold (secondary)
ERROR = "#ba1a1a"        # Red
WARNING = "#feb700"      # Amber
SUCCESS = "#4ade80"      # Green
BG_DARK = "#121317"
BG_LIGHT = "#f8f9fa"
SURFACE = "#ffffff"
TEXT_DARK = "#191c1d"
TEXT_LIGHT = "#e3e2e7"

# Fonts
try:
    FONT_HEADLINE = ImageFont.truetype("arialbd.ttf", 48)  # Hanken Grotesk substitute
    FONT_BODY = ImageFont.truetype("arial.ttf", 24)        # Inter substitute
    FONT_SMALL = ImageFont.truetype("arial.ttf", 18)
except:
    FONT_HEADLINE = ImageFont.load_default()
    FONT_BODY = ImageFont.load_default()
    FONT_SMALL = ImageFont.load_default()

def draw_shield(draw, center, size, fill, outline=None):
    """Draw a shield shape."""
    x, y = center
    r = size
    points = [
        (x, y - r),                                    # top
        (x + r * 0.7, y - r * 0.3),                   # right upper
        (x + r * 0.7, y + r * 0.4),                   # right lower
        (x, y + r),                                    # bottom point
        (x - r * 0.7, y + r * 0.4),                   # left lower
        (x - r * 0.7, y - r * 0.3),                   # left upper
    ]
    draw.polygon(points, fill=fill, outline=outline)

def create_screenshot_1():
    """Screenshot 1: Main scan view with results."""
    W, H = 1280, 800
    img = Image.new("RGB", (W, H), BG_LIGHT)
    draw = ImageDraw.Draw(img)
    
    # Side panel (320px wide)
    panel_w = 320
    draw.rectangle([0, 0, panel_w, H], fill=SURFACE)
    draw.rectangle([panel_w, 0, panel_w + 1, H], fill="#e1e3e4")
    
    # Top app bar
    draw.rectangle([0, 0, panel_w, 64], fill=SURFACE)
    draw.text((24, 16), "Traba-Hero", fill=PRIMARY, font=FONT_HEADLINE)
    
    # Scan view content
    y = 100
    # Scan button
    btn_rect = [24, y, panel_w - 24, y + 56]
    draw.rounded_rectangle(btn_rect, radius=8, fill=ACCENT)
    draw.text((panel_w//2 - 60, y + 12), "Pick a Job Post", fill="white", font=FONT_BODY)
    
    # Results card
    y += 100
    card_rect = [24, y, panel_w - 24, y + 200]
    draw.rounded_rectangle(card_rect, radius=12, fill=SURFACE, outline="#e1e3e4", width=1)
    # Hard shadow
    draw.rectangle([28, y + 4, panel_w - 20, y + 204], fill="#00000040")
    draw.rectangle([24, y, panel_w - 24, y + 200], fill=SURFACE, outline="#e1e3e4", width=1)
    
    # Risk level badge
    badge_rect = [40, y + 20, 180, y + 60]
    draw.rounded_rectangle(badge_rect, radius=20, fill=ERROR)
    draw.text((60, y + 28), "CRITICAL", fill="white", font=FONT_BODY)
    
    # Anomaly cards
    for i, (title, desc) in enumerate([
        ("Upfront Fee", "Asks for 500 PHP deposit to start"),
        ("Free Email", "Uses gmail.com not company domain"),
        ("No Permit", "No business permit shown"),
    ]):
        ay = y + 80 + i * 40
        draw.text((40, ay), title, fill=ERROR, font=FONT_SMALL)
        draw.text((40, ay + 22), desc, fill="#666", font=FONT_SMALL)
    
    # Web page preview (right side)
    draw.rectangle([panel_w, 0, W, H], fill="#f0f0f0")
    # Mock job posting
    draw.rectangle([panel_w + 40, 80, W - 40, 400], fill="white", outline="#ddd", width=1)
    draw.text((panel_w + 60, 100), "Data Entry Specialist - Work From Home", fill=TEXT_DARK, font=FONT_HEADLINE)
    draw.text((panel_w + 60, 160), "Earn 50,000/week! No experience needed.", fill=TEXT_DARK, font=FONT_BODY)
    draw.text((panel_w + 60, 200), "Just pay 500 PHP registration fee to start", fill=ERROR, font=FONT_BODY)
    draw.text((panel_w + 60, 250), "Contact: hr@company@gmail.com", fill=TEXT_DARK, font=FONT_BODY)
    
    img.save(os.path.join(OUT_DIR, "screenshot_1_scan_results.png"))
    return img

def create_screenshot_2():
    """Screenshot 2: Employer verification."""
    W, H = 1280, 800
    img = Image.new("RGB", (W, H), BG_LIGHT)
    draw = ImageDraw.Draw(img)
    
    panel_w = 320
    draw.rectangle([0, 0, panel_w, H], fill=SURFACE)
    draw.rectangle([panel_w, 0, panel_w + 1, H], fill="#e1e3e4")
    
    # Verification results
    y = 100
    draw.text((24, y), "Employer Verification", fill=PRIMARY, font=FONT_HEADLINE)
    
    checks = [
        ("Company Existence", "GREEN", "Found: NAILS GLOW registered"),
        ("Official Registration", "YELLOW", "No SEC/DTI filing found"),
        ("Reputation", "GREEN", "No scam reports found"),
        ("Channel Match", "RED", "Email uses gmail.com"),
        ("Location", "GREEN", "Matches: Pampanga branches"),
    ]
    
    for label, status, detail in checks:
        y += 60
        # Status dot
        color = SUCCESS if status == "GREEN" else (WARNING if status == "YELLOW" else ERROR)
        draw.ellipse([24, y + 6, 40, y + 22], fill=color)
        draw.text((50, y + 4), label, fill=TEXT_DARK, font=FONT_BODY)
        draw.text((50, y + 30), detail, fill=color, font=FONT_SMALL)
    
    # Action block
    y += 100
    draw.rectangle([24, y, panel_w - 24, y + 80], fill="#fff0f0", outline=ERROR, width=1)
    draw.text((40, y + 10), "Do not send money", fill=ERROR, font=FONT_BODY)
    draw.text((40, y + 40), "This posting asks for upfront payment.", fill=ERROR, font=FONT_SMALL)
    
    img.save(os.path.join(OUT_DIR, "screenshot_2_verification.png"))
    return img

def create_screenshot_3():
    """Screenshot 3: Resume match view."""
    W, H = 1280, 800
    img = Image.new("RGB", (W, H), BG_LIGHT)
    draw = ImageDraw.Draw(img)
    
    panel_w = 320
    draw.rectangle([0, 0, panel_w, H], fill=SURFACE)
    draw.rectangle([panel_w, 0, panel_w + 1, H], fill="#e1e3e4")
    
    y = 100
    draw.text((24, y), "Resume Match", fill=PRIMARY, font=FONT_HEADLINE)
    
    # Upload area
    y += 60
    draw.rounded_rectangle([24, y, panel_w - 24, y + 100], radius=12, fill="#f5f5f5", outline="#ddd", width=2)
    draw.text((panel_w//2 - 70, y + 30), "Upload Resume", fill=TEXT_DARK, font=FONT_BODY)
    draw.text((panel_w//2 - 80, y + 60), "PDF, DOCX, TXT, PNG, JPG", fill="#888", font=FONT_SMALL)
    
    # Match results
    y += 140
    matches = [
        ("Customer Service Rep", "BPO Global Inc.", "HIGH", SUCCESS, "85%"),
        ("Data Entry Specialist", "Tech Solutions PH", "HIGH", SUCCESS, "78%"),
        ("Sales Representative", "RCBC Savings Bank", "MODERATE", WARNING, "62%"),
    ]
    
    for title, company, risk, color, score in matches:
        draw.rounded_rectangle([24, y, panel_w - 24, y + 80], radius=8, fill=SURFACE, outline="#e1e3e4", width=1)
        draw.text((40, y + 10), title, fill=TEXT_DARK, font=FONT_BODY)
        draw.text((40, y + 38), company, fill="#666", font=FONT_SMALL)
        # Risk badge
        badge = [panel_w - 100, y + 10, panel_w - 30, y + 38]
        draw.rounded_rectangle(badge, radius=12, fill=color)
        draw.text((panel_w - 90, y + 14), risk, fill="white", font=FONT_SMALL)
        # Score
        draw.text((panel_w - 90, y + 48), score, fill=color, font=FONT_HEADLINE)
        y += 95
    
    img.save(os.path.join(OUT_DIR, "screenshot_3_resume_match.png"))
    return img

def create_promo_tile():
    """Promo tile 440x280."""
    W, H = 440, 280
    img = Image.new("RGB", (W, H), PRIMARY)
    draw = ImageDraw.Draw(img)
    
    # Shield icon
    draw_shield(draw, (W//2, H//2 - 20), 60, fill="white")
    # Briefcase + magnifier simplified
    draw.rectangle([W//2 - 15, H//2 - 10, W//2 + 15, H//2 + 20], fill=PRIMARY)
    draw.rectangle([W//2 - 5, H//2 - 20, W//2 + 5, H//2 - 5], fill=PRIMARY)
    # Magnifier
    draw.ellipse([W//2 + 20, H//2 + 5, W//2 + 45, H//2 + 30], outline="white", width=3)
    draw.line([W//2 + 38, H//2 + 23, W//2 + 50, H//2 + 35], fill="white", width=3)
    
    draw.text((W//2, H - 50), "Traba-Hero", fill="white", font=FONT_HEADLINE, anchor="mm")
    draw.text((W//2, H - 15), "Job Scam Protection", fill="#b0c6ff", font=FONT_BODY, anchor="mm")
    
    img.save(os.path.join(OUT_DIR, "promo_tile_440x280.png"))
    return img

def create_marquee():
    """Marquee 1400x560."""
    W, H = 1400, 560
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    
    # Left: Shield icon
    draw_shield(draw, (200, H//2), 120, fill=PRIMARY, outline=ACCENT)
    # Briefcase + magnifier
    draw.rectangle([170, H//2 - 20, 230, H//2 + 40], fill=BG_DARK)
    draw.rectangle([190, H//2 - 40, 210, H//2 - 5], fill=BG_DARK)
    draw.ellipse([240, H//2 + 10, 290, H//2 + 60], outline=ACCENT, width=5)
    draw.line([275, H//2 + 45, 310, H//2 + 80], fill=ACCENT, width=5)
    
    # Right: Text
    draw.text((400, H//2 - 80), "Traba-Hero", fill="white", font=ImageFont.truetype("arialbd.ttf", 72) if True else FONT_HEADLINE)
    draw.text((400, H//2 + 10), "Scan job postings for scam signals", fill="#b0c6ff", font=FONT_BODY)
    draw.text((400, H//2 + 60), "Verify employers • Match your resume • Stay safe", fill="#888", font=FONT_BODY)
    
    # CTA button
    btn = [400, H//2 + 130, 600, H//2 + 190]
    draw.rounded_rectangle(btn, radius=12, fill=ACCENT)
    draw.text((500, H//2 + 145), "Add to Chrome", fill="white", font=FONT_BODY, anchor="mm")
    
    img.save(os.path.join(OUT_DIR, "marquee_1400x560.png"))
    return img

def copy_icon():
    """Copy 128x128 icon to assets folder."""
    src = r"E:\traba-hero\.output\chrome-mv3\icon\128.png"
    dst = os.path.join(OUT_DIR, "icon_128x128.png")
    if os.path.exists(src):
        Image.open(src).save(dst)
        print(f"Copied {src} -> {dst}")

if __name__ == "__main__":
    print("Generating Chrome Web Store assets...")
    create_screenshot_1()
    print("Created screenshot_1_scan_results.png")
    create_screenshot_2()
    print("Created screenshot_2_verification.png")
    create_screenshot_3()
    print("Created screenshot_3_resume_match.png")
    create_promo_tile()
    print("Created promo_tile_440x280.png")
    create_marquee()
    print("Created marquee_1400x560.png")
    copy_icon()
    print(f"\nAll assets saved to {OUT_DIR}")
    for f in os.listdir(OUT_DIR):
        print(f"  {f}")