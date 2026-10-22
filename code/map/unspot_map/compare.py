"""Side-by-side review crops: source | version A | version B in ONE frame (map/rules/81; map/rules/80 §9.2).

Looking at the whole plan at 1:4 hides the defects that differed between v1 and v2 (a doubled wall,
a stroke along a virtual edge, a desk inside a wall). The review protocol is a fixed list of crops, each
rendered from every version into the same source-frame box - see REVIEW_SPOTS in the report."""
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

try:
    FONT = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 18)
except OSError:
    FONT = ImageFont.load_default()


def panel(img_bgr, frame_to_img, box, scale):
    """crop `box` (x0, y0, x1, y1 in the common frame) from an image given frame_to_img (frame.Affine)"""
    x0, y0, x1, y1 = box; W = int((x1 - x0) * scale); H = int((y1 - y0) * scale)
    S = np.array([[1 / scale, 0, x0], [0, 1 / scale, y0], [0, 0, 1.0]])
    T = frame_to_img.M @ S
    out = cv2.warpAffine(img_bgr, T[:2], (W, H), flags=cv2.WARP_INVERSE_MAP | (cv2.INTER_AREA if scale < 2 else cv2.INTER_CUBIC),
                         borderValue=(255, 255, 255))
    return Image.fromarray(out[:, :, ::-1])


def row(panels, captions, width=2400, gap=16):
    n = len(panels); w = (width - gap * (n + 1)) // n
    ims = [p.resize((w, int(p.height * w / p.width)), Image.LANCZOS) for p in panels]
    R = Image.new('RGB', (width, max(i.height for i in ims) + 40), 'white'); d = ImageDraw.Draw(R); x = gap
    for im, c in zip(ims, captions):
        R.paste(im, (x, 34)); d.rectangle([x, 34, x + im.width - 1, 34 + im.height - 1], outline=(210, 214, 220))
        d.text((x + 4, 6), c, fill=(60, 64, 80), font=FONT); x += im.width + gap
    return R


def stack(rows, out_png):
    W = max(r.width for r in rows); H = sum(r.height for r in rows)
    out = Image.new('RGB', (W, H), 'white'); y = 0
    for r in rows:
        out.paste(r, (0, y)); y += r.height
    out.save(out_png, optimize=True)
    return out.size


def question_tile(images, frame_to_imgs, box, marks, captions, question, out_png, scale=2.0, width=2400):
    """Picture for an owner question (map/rules/50 §2, core/rules/20 §1; decision 02.10.2026): the SAME frame box from every
    image (source | current map | variant ...), the place outlined in red in each panel, the question on top.
    images — BGR arrays; frame_to_imgs — frame.Affine per image; box — (x0, y0, x1, y1) in the common frame;
    marks — [(x, y, r)] circles or [(x0, y0, x1, y1)] boxes in the frame. Returns the PNG size.
    The picture goes with an interactive question in the chat (options = the variants shown), never instead of it."""
    x0, y0 = box[0], box[1]
    ps = []
    for img, A in zip(images, frame_to_imgs):
        p = panel(img, A, box, scale); d = ImageDraw.Draw(p)
        for m in marks:
            if len(m) == 3:
                cx, cy, r = [(m[0] - x0) * scale, (m[1] - y0) * scale, m[2] * scale]
                d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(230, 30, 30), width=4)
            else:
                d.rectangle([(m[0] - x0) * scale, (m[1] - y0) * scale, (m[2] - x0) * scale, (m[3] - y0) * scale], outline=(230, 30, 30), width=4)
        ps.append(p)
    R = row(ps, captions, width=width)
    head = Image.new('RGB', (R.width, 56), 'white'); ImageDraw.Draw(head).text((16, 16), question, fill=(20, 20, 30), font=FONT)
    return stack([head, R], out_png)
