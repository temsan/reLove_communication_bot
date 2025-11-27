"""
Конвертация SVG логотипа в PNG для ватермарка
"""
from cairosvg import svg2png
from pathlib import Path

svg_path = Path("data/watermark/relove_logo.svg")
png_path = Path("data/watermark/relove_logo.png")

png_path.parent.mkdir(parents=True, exist_ok=True)

svg2png(
    url=str(svg_path),
    write_to=str(png_path),
    output_width=200,
    output_height=200
)

print(f"✓ Конвертировано: {png_path}")
