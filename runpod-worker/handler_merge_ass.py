import json
import sys

INPUT_JSON = sys.argv[1]
OUTPUT_ASS = sys.argv[2]

# =============================
# STYLE CONFIG (TU ESTILO)
# =============================

FONT_NAME = "Poppins ExtraBold"
FONT_SIZE = 120

PRIMARY_COLOR = "&H00FFFFFF"   # blanco
HIGHLIGHT_COLOR = "&H0000FFFF" # amarillo
OUTLINE_COLOR = "&H00000000"   # negro

OUTLINE = 8
SHADOW = 0

ALIGNMENT = 2        # centrado abajo
MARGIN_L = 80
MARGIN_R = 80
MARGIN_V = 120

# =============================
# TIME UTILS
# =============================

def sec_to_ass(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"

# =============================
# LOAD WORDS
# =============================

with open(INPUT_JSON, "r", encoding="utf-8") as f:
    words = json.load(f)

if not words:
    raise RuntimeError("No words found for ASS generation")

# =============================
# ASS HEADER
# =============================

ass = []
ass.append("[Script Info]")
ass.append("ScriptType: v4.00+")
ass.append("PlayResX: 1080")
ass.append("PlayResY: 1920")
ass.append("")
ass.append("[V4+ Styles]")
ass.append(
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
    "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
    "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
    "Alignment, MarginL, MarginR, MarginV, Encoding"
)
ass.append(
    f"Style: Default,{FONT_NAME},{FONT_SIZE},"
    f"{PRIMARY_COLOR},{PRIMARY_COLOR},{OUTLINE_COLOR},&H00000000,"
    f"1,0,0,0,100,100,0,0,1,{OUTLINE},{SHADOW},"
    f"{ALIGNMENT},{MARGIN_L},{MARGIN_R},{MARGIN_V},1"
)

ass.append("")
ass.append("[Events]")
ass.append(
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
)

# =============================
# EVENTS (WORD BY WORD)
# =============================

for w in words:
    start = sec_to_ass(w["start"])
    end = sec_to_ass(max(w["end"], w["start"] + 0.05))  # seguridad
    text = w["word"].replace("{", "").replace("}", "")

    ass.append(
        f"Dialogue: 0,{start},{end},Default,,0,0,0,,"
        f"{{\\c{HIGHLIGHT_COLOR}}}{text}"
    )

# =============================
# WRITE FILE
# =============================

with open(OUTPUT_ASS, "w", encoding="utf-8") as f:
    f.write("\n".join(ass))

print(f"[OK] ASS generado con {len(words)} palabras")
