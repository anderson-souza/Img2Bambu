from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from .params import Params, Palette


@dataclass
class Analysis:
    rgba: np.ndarray        # cropped to silhouette bbox
    sil: np.ndarray         # bool, same shape as rgba[..., 0]
    labels: np.ndarray      # int, -1 outside silhouette
    palette: Palette
    note: str = ""


def load_image(path):
    return np.array(Image.open(path).convert("RGBA"))


def silhouette(rgba, params):
    alpha = rgba[..., 3]
    note = ""
    mode = params.background
    if mode == "alpha" and alpha.min() > 128:
        mode, note = "color", "Imagem sem transparência: fundo removido pela cor dos cantos."
    if mode == "alpha":
        return alpha > 128, note
    rgb = np.ascontiguousarray(rgba[..., :3])
    h, w = rgb.shape[:2]
    bg = np.zeros((h + 2, w + 2), np.uint8)
    tol = (params.bg_tolerance,) * 3
    for seed in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        if bg[seed[1] + 1, seed[0] + 1]:
            continue
        cv2.floodFill(rgb.copy(), bg, seed, (0, 0, 0), tol, tol,
                      4 | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255 << 8))
    return (bg[1:-1, 1:-1] == 0) & (alpha > 128), note


def _crop(rgba, sil):
    ys, xs = np.nonzero(sil)
    if len(xs) == 0:
        raise ValueError("Nenhum pixel do objeto encontrado (imagem vazia ou fundo não removido).")
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    return rgba[y0:y1, x0:x1].copy(), sil[y0:y1, x0:x1].copy()


def _to_lab(rgb_rows):
    return cv2.cvtColor(rgb_rows.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)


def kmeans_palette(rgba, sil, n, seed=0):
    rgb = rgba[..., :3][sil]
    lab = _to_lab(rgb)
    rng = np.random.default_rng(seed)
    sample = lab[rng.choice(len(lab), min(len(lab), 120_000), replace=False)]
    cv2.setRNGSeed(seed)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.5)
    _, _, centers = cv2.kmeans(sample, n, None, crit, 4, cv2.KMEANS_PP_CENTERS)
    d = ((lab[:, None, :] - centers[None, :, :]) ** 2).sum(-1)
    lab_labels = d.argmin(1)
    # why: stable ordering (dark -> light) keeps label ids deterministic across runs
    order = np.argsort(centers[:, 0])
    remap = np.empty(n, int); remap[order] = np.arange(n)
    lab_labels = remap[lab_labels]
    labels = np.full(sil.shape, -1, int)
    labels[sil] = lab_labels
    colors = []
    for i in range(n):
        m = rgb[lab_labels == i]
        colors.append(tuple(int(c) for c in (np.median(m, 0) if len(m) else (128, 128, 128))))
    return labels, colors


def suggest_base(labels, sil, n):
    ring = sil & ~cv2.erode(sil.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    counts = np.bincount(labels[ring], minlength=n)
    return int(counts.argmax())


def suggest_streak(colors):
    # why: highlights in rendered art are near-white, so only light low-saturation colors get the filter by default
    hsv = [cv2.cvtColor(np.uint8([[c]]), cv2.COLOR_RGB2HSV)[0, 0] for c in colors]
    return {i for i, v in enumerate(hsv) if v[1] < 60 and v[2] > 150}


def analyze(path_or_rgba, params: Params):
    rgba = load_image(path_or_rgba) if isinstance(path_or_rgba, str) else path_or_rgba
    sil, note = silhouette(rgba, params)
    rgba, sil = _crop(rgba, sil)
    labels, colors = kmeans_palette(rgba, sil, params.n_colors)
    pal = Palette(colors=colors, base_index=suggest_base(labels, sil, len(colors)),
                  streak=suggest_streak(colors))
    return Analysis(rgba, sil, labels, pal, note)


def mm_per_px(an: Analysis, params: Params):
    return params.width_mm / an.sil.shape[1]


def clean(mask, params, mpp, open_mm, min_area_mm2, hole_mm2):
    ups = params.upsample
    h, w = mask.shape
    m = cv2.resize(mask.astype(np.uint8) * 255, (w * ups, h * ups), interpolation=cv2.INTER_LINEAR)
    m = cv2.GaussianBlur(m, (0, 0), ups * 0.8)
    m = (m > 127).astype(np.uint8)
    k_px = int(round(open_mm / mpp)) * ups
    if k_px >= 2:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_px, k_px))
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k)
    px_area = (mpp / ups) ** 2
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    keep = np.zeros(n, bool); keep[1:] = st[1:, cv2.CC_STAT_AREA] * px_area >= min_area_mm2
    m = keep[lab].astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(1 - m, 4)
    small = np.zeros(n, bool); small[1:] = st[1:, cv2.CC_STAT_AREA] * px_area < hole_mm2
    m[small[lab]] = 1
    return m


def drop_streaks(m, mpp_up, radius_mm):
    n, lab = cv2.connectedComponents(m, 8)
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 5) * mpp_up
    rmax = np.zeros(n); np.maximum.at(rmax, lab.ravel(), dt.ravel())
    keep = rmax >= radius_mm; keep[0] = False
    return keep[lab].astype(np.uint8)


def build_masks(an: Analysis, palette: Palette, params: Params):
    """Returns (silhouette_mask, {label: mask}) at upsampled resolution; raised masks are disjoint."""
    mpp = mm_per_px(an, params)
    d = params.min_detail_mm
    sil_m = clean(an.sil, params, mpp, d, 2.0, 1.0)
    lut = np.array([palette.resolve(i) for i in range(len(palette.colors))] + [-1])
    resolved = lut[an.labels]          # label -1 indexes the trailing -1 sentinel
    masks, taken = {}, np.zeros_like(sil_m)
    streak = palette.streak
    for c in palette.active():
        if c == palette.base_index:
            continue
        m = clean(resolved == c, params, mpp, d, 0.3, 0.15) & sil_m & (1 - taken)
        if c in streak and params.streak_radius_mm > 0:
            m = drop_streaks(m.astype(np.uint8), mpp / params.upsample, params.streak_radius_mm)
        if m.any():
            masks[c] = m
            taken |= m
    return sil_m, masks


def preview(sil_m, masks, palette, bg=(255, 255, 255)):
    img = np.empty(sil_m.shape + (3,), np.uint8); img[:] = bg
    img[sil_m == 1] = palette.colors[palette.base_index]
    for c, m in masks.items():
        img[m == 1] = palette.colors[c]
    return img
