"""
显示 data/data-1/tif/ 目录下的图像（扩展名为 .tif，但实际格式混杂）。

文件格式情况：
  - 部分是真正的 TIFF（uint16，值域 0~256）
  - 部分伪装成 .tif 的 PNG（uint16）
  - 部分是 12-bit JPEG（需要 imageio + imagecodecs 才能读取）

黑图原因：uint16 数据实际值只在 0~256，查看器按 0~65535 全范围拉伸，显示几乎全黑。
解决方案：百分位数线性拉伸到 0~255 uint8 再显示。
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

TIF_DIR = Path(__file__).parent.parent / "data" / "data-1" / "tif"
OUT_DIR = Path(__file__).parent.parent / "data" / "data-1" / "tif_preview"
OUT_DIR.mkdir(exist_ok=True)


def stretch(data: np.ndarray, low_pct: float = 2.0, high_pct: float = 98.0) -> np.ndarray:
    """百分位数线性拉伸到 0~255 uint8。"""
    lo = np.percentile(data, low_pct)
    hi = np.percentile(data, high_pct)
    if hi == lo:
        return np.zeros_like(data, dtype=np.uint8)
    scaled = (data.astype(np.float32) - lo) / (hi - lo) * 255.0
    return np.clip(scaled, 0, 255).astype(np.uint8)


def read_image(path: Path) -> np.ndarray:
    """读取图像，自动处理 TIFF/PNG/12-bit JPEG 等格式。"""
    try:
        return np.array(Image.open(path))
    except Exception:
        # 尝试 imageio（支持 12-bit JPEG，需要 imagecodecs）
        try:
            import imageio
            return np.array(imageio.imread(path))
        except Exception as e:
            raise RuntimeError(f"无法读取文件（可能是 12-bit JPEG，需安装 imagecodecs）: {e}")


def process(path: Path) -> Image.Image:
    data = read_image(path)
    if data.ndim == 3:
        data = data[:, :, 0]  # 取第一通道
    stretched = stretch(data)
    return Image.fromarray(stretched, mode="L")


def make_grid(images: list[tuple[str, Image.Image]], cols: int = 3) -> Image.Image:
    """将多张图拼成网格，带文件名标注。"""
    thumb_w, thumb_h = 400, 320
    label_h = 30
    rows = (len(images) + cols - 1) // cols
    grid = Image.new("L", (cols * thumb_w, rows * (thumb_h + label_h)), color=30)

    for i, (name, img) in enumerate(images):
        col, row = i % cols, i // cols
        thumb = img.resize((thumb_w, thumb_h), Image.LANCZOS)
        x, y = col * thumb_w, row * (thumb_h + label_h)
        grid.paste(thumb, (x, y))

        # 在缩略图下方写文件名（取前 30 个字符）
        draw = ImageDraw.Draw(grid)
        label = name[:35] + ("…" if len(name) > 35 else "")
        draw.text((x + 4, y + thumb_h + 4), label, fill=200)

    return grid


def main():
    tif_files = sorted(TIF_DIR.glob("*.tif"))
    if not tif_files:
        print(f"未找到 TIFF 文件：{TIF_DIR}")
        return

    processed = []
    for tif_path in tif_files:
        print(f"处理: {tif_path.name}")
        try:
            img = process(tif_path)
        except RuntimeError as e:
            print(f"  ✗ 跳过: {e}")
            continue

        # 保存单张预览
        out_name = tif_path.stem + "_preview.png"
        out_path = OUT_DIR / out_name
        img.save(out_path)
        print(f"  → 已保存: {out_path}")

        processed.append((tif_path.name, img))

    # 拼接网格总览并打开
    grid = make_grid(processed, cols=3)
    grid_path = OUT_DIR / "overview.png"
    grid.save(grid_path)
    print(f"\n总览图已保存: {grid_path}")
    grid.show(title="TIFF 预览总览")


if __name__ == "__main__":
    main()
