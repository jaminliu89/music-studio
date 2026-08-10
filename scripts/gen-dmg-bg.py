#!/usr/bin/env python3
"""ToneLab DMG 背景图 1000x600，坐标与 dmgbuild-settings.py 对齐"""
from PIL import Image, ImageDraw, ImageFont
import os, sys

W, H = 1000, 600
BG = (247, 240, 224)      # 米黄
INK = (55, 50, 40)         # 主字
DIM = (140, 130, 110)      # 副字
FAINT = (215, 205, 185)    # 分隔线
ACCENT = (201, 112, 94)    # 珊瑚色（ToneLab 强调色）

img = Image.new('RGB', (W, H), BG)
d = ImageDraw.Draw(img)

CANDS = [
    '/System/Library/Fonts/PingFang.ttc',
    '/System/Library/Fonts/STHeiti Medium.ttc',
    '/System/Library/Fonts/Hiragino Sans GB.ttc',
]
fp = next((p for p in CANDS if os.path.exists(p)), None)
if not fp:
    raise SystemExit('no CJK font')

f_title = ImageFont.truetype(fp, 40)
f_sub = ImageFont.truetype(fp, 18)
f_hint = ImageFont.truetype(fp, 15)

# 顶部标题
d.text((W // 2, 65), 'ToneLab', font=f_title, fill=INK, anchor='mm')
d.text((W // 2, 108), 'AI 音乐生成 · 音调工坊', font=f_sub, fill=DIM, anchor='mm')
d.line([(280, 145), (W - 280, 145)], fill=FAINT, width=1)

# 主拖拽箭头（app 200,230 → Applications 700,230，箭头在下方 y=350）
arrow_y = 350
d.line([(310, arrow_y), (620, arrow_y)], fill=ACCENT, width=2)
d.polygon([(620, arrow_y - 8), (620, arrow_y + 8), (640, arrow_y)], fill=ACCENT)
d.text(((310 + 640) // 2, arrow_y + 25), '拖入 Applications 完成安装', font=f_hint, fill=INK, anchor='mm')

# 底部分隔 + 提示
d.line([(280, 420), (W - 280, 420)], fill=FAINT, width=1)
d.text((W // 2, 545), '首次打开如提示无法验证开发者，请到 系统设置 → 隐私与安全性 允许',
       font=f_hint, fill=DIM, anchor='mm')

out = sys.argv[1] if len(sys.argv) > 1 else 'dmg-bg.png'
img.save(out, 'PNG', optimize=True)
img.resize((W * 2, H * 2), Image.LANCZOS).save(out.replace('.png', '@2x.png'), 'PNG', optimize=True)
print(f'✓ {out} + @2x')
