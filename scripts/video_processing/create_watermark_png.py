"""
Создание PNG ватермарка со спиралью
"""
from PIL import Image, ImageDraw
from pathlib import Path
import math

# Создаем изображение с прозрачным фоном
size = 200
img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Параметры спирали
center_x, center_y = size // 2, size // 2
color = (255, 255, 255, 180)  # Белый с прозрачностью
width = 8

# Рисуем спираль
points = []
for i in range(0, 360 * 3, 5):  # 3 оборота
    angle = math.radians(i)
    radius = 10 + (i / 10)  # Увеличивающийся радиус
    x = center_x + radius * math.cos(angle)
    y = center_y + radius * math.sin(angle)
    points.append((x, y))

# Рисуем линию спирали
for i in range(len(points) - 1):
    draw.line([points[i], points[i + 1]], fill=color, width=width)

# Центральная точка
draw.ellipse(
    [center_x - 12, center_y - 12, center_x + 12, center_y + 12],
    fill=(255, 255, 255, 200)
)

# Сохраняем
output_path = Path("data/watermark/relove_logo.png")
output_path.parent.mkdir(parents=True, exist_ok=True)
img.save(output_path, 'PNG')

print(f"✓ Ватермарк создан: {output_path}")
