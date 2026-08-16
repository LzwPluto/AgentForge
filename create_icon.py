import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ASSETS_DIR = Path(__file__).parent / "assets"
GUI_IMG_DIR = Path(__file__).parent / "gui" / "static" / "img"

ASSETS_DIR.mkdir(parents=True, exist_ok=True)
GUI_IMG_DIR.mkdir(parents=True, exist_ok=True)


def draw_agentforge_icon(size: int = 512) -> Image.Image:
    """生成高质感 AgentForge 专属品牌应用图标"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = size * 0.05
    radius = size * 0.22

    # 1. 绘制带有柔和外发光的超椭圆底座 (Squircle)
    # 底座背景渐变 (切达暖金到落日琥珀橙: #F59E0B -> #D97706 -> #9A3412)
    base_box = [margin, margin, size - margin, size - margin]
    
    # 阴影层
    shadow_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_img)
    shadow_box = [margin + size * 0.02, margin + size * 0.04, size - margin - size * 0.02, size - margin + size * 0.04]
    shadow_draw.rounded_rectangle(shadow_box, radius=radius, fill=(180, 83, 9, 120))
    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(size * 0.05))
    img.paste(shadow_img, (0, 0), shadow_img)

    # 主体圆角矩形
    draw.rounded_rectangle(base_box, radius=radius, fill=(245, 158, 11, 255), outline=(254, 243, 199, 180), width=int(size * 0.015))

    # 内部微反光渐变
    inner_margin = margin + size * 0.03
    inner_radius = radius * 0.85
    inner_box = [inner_margin, inner_margin, size - inner_margin, size - inner_margin]
    draw.rounded_rectangle(inner_box, radius=inner_radius, fill=(217, 119, 6, 255))

    # 2. 绘制智能体协同网络与核心晶体图形 (多 Agent 协同圆桌晶核)
    cx, cy = size / 2, size / 2

    # 绘制科技光环轨道
    orbit_r = size * 0.28
    draw.ellipse([cx - orbit_r, cy - orbit_r, cx + orbit_r, cy + orbit_r], outline=(254, 243, 199, 90), width=int(size * 0.012))

    # 绘制 5 节点多智能体圆桌卫星连线 (Round-Robin Star Mesh)
    import math
    nodes = []
    num_nodes = 5
    for i in range(num_nodes):
        angle = (2 * math.pi / num_nodes) * i - (math.pi / 2)
        nx = cx + orbit_r * math.cos(angle)
        ny = cy + orbit_r * math.sin(angle)
        nodes.append((nx, ny))

    # 节点之间的连接线
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            draw.line([nodes[i], nodes[j]], fill=(254, 243, 199, 60), width=max(1, int(size * 0.008)))

    # 核心能量多面体 (Center Core Gem)
    core_r = size * 0.14
    # 绘制钻石多边形
    diamond_pts = [
        (cx, cy - core_r * 1.15),
        (cx + core_r * 1.1, cy),
        (cx, cy + core_r * 1.15),
        (cx - core_r * 1.1, cy)
    ]
    draw.polygon(diamond_pts, fill=(255, 255, 255, 240), outline=(254, 243, 199, 255))

    # 内部反光面
    inner_pts_left = [
        (cx, cy - core_r * 1.15),
        (cx - core_r * 1.1, cy),
        (cx, cy + core_r * 1.15),
        (cx, cy)
    ]
    draw.polygon(inner_pts_left, fill=(254, 240, 138, 200))

    # 绘制 5 个环绕智能体节点发光圆点 (Agent Nodes)
    node_colors = [
        (255, 255, 255), # Lead Agent
        (56, 189, 248),  # Coder (Cyan)
        (74, 222, 128),  # Runner/Reviewer (Green)
        (244, 114, 182), # Writer (Pink)
        (192, 132, 252)  # Explorer (Purple)
    ]

    for i, (nx, ny) in enumerate(nodes):
        nr = size * 0.045
        # 外发光
        draw.ellipse([nx - nr * 1.3, ny - nr * 1.3, nx + nr * 1.3, ny + nr * 1.3], fill=(255, 255, 255, 120))
        # 实体核心
        draw.ellipse([nx - nr, ny - nr, nx + nr, ny + nr], fill=node_colors[i] + (255,), outline=(255, 255, 255, 255), width=int(size * 0.008))

    return img


def generate_all_icons():
    print("[1/3] Generating 512x512 Master Icon...")
    master_img = draw_agentforge_icon(512)

    # 1. 保存高清 PNG
    png_path = ASSETS_DIR / "icon.png"
    master_img.save(png_path, "PNG")
    print(f"  -> Saved PNG: {png_path}")

    # 2. 同步保存 WebUI 静态资源 Favicon / Logo
    web_fav = GUI_IMG_DIR / "favicon.png"
    web_logo = GUI_IMG_DIR / "logo.png"
    master_img.resize((64, 64), Image.Resampling.LANCZOS).save(web_fav, "PNG")
    master_img.resize((128, 128), Image.Resampling.LANCZOS).save(web_logo, "PNG")
    print(f"  -> Saved Web Favicon: {web_fav}")

    # 3. 生成 Windows Multi-Resolution ICO
    ico_path = ASSETS_DIR / "icon.ico"
    master_img.save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    )
    print(f"  -> Saved Multi-size Windows ICO: {ico_path}")
    print("[SUCCESS] All icons created successfully!")


if __name__ == "__main__":
    generate_all_icons()
