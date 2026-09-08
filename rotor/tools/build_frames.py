#!/usr/bin/env python3
"""
build_frames.py — genera la secuencia de fotogramas del despiece a partir del
vídeo original.

Dev-time only. No se despliega. Requiere:
    pip install imageio-ffmpeg pillow numpy

Qué hace, en orden:

1. Extrae con ffmpeg los fotogramas del tramo util del vídeo (el arranque es un
   macro de la esfera que no sirve como plano inicial: el despiece empieza
   despues).
2. Elimina la marca de agua del generador de vídeo. No usa `delogo` de ffmpeg
   porque ese filtro interpola desde el borde de la caja y destruye las piezas
   que cruzan por esa zona (la corona dorada, hacia el frame 60). En su lugar:
      a. Estima el alfa de la marca por pixel con el minimo temporal de todos
         los fotogramas (el fondo detras del logo es negro en la mayoria, asi
         que el minimo tiende a alpha*255).
      b. Rellena la mascara con interpolacion direccional: cada hueco se
         interpola por columnas y por filas entre los pixeles conocidos mas
         cercanos, y ambas estimaciones se mezclan ponderando por el inverso
         de la distancia. Preserva la estructura (bordes, degradados) en vez
         de promediar toda la caja, que es lo que producia bandas.

   Probado tambien y descartado: deshacer la composicion alfa
   (bg = (px - alpha*255)/(1 - alpha)). Sobre fondo negro puro funciona, pero
   el fondo real no es negro puro (hay vineta y estrellas) y la resta deja un
   fantasma legible del texto.
3. Remuestrea a FRAME_COUNT fotogramas repartidos uniformemente.
4. Exporta dos secuencias WebP: escritorio y movil.

Uso:
    python tools/build_frames.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

# --- Configuracion ---------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)

SOURCE_VIDEO = os.path.join(os.path.dirname(PROJECT), "benyar", "video-fondo.mp4")

# El vídeo dura 5,04 s. Los primeros 0,62 s son un macro de la esfera con el
# fondo claro: no encaja como plano de apertura ni como "reloj montado".
START_SECONDS = 0.62

FRAME_COUNT = 100

SIZES = [
    # (subcarpeta, ancho, calidad webp)
    ("d", 1200, 74),
    ("m", 720, 72),
]

# Caja generosa alrededor de la marca de agua (x0, y0, x1, y1) en px del origen.
LOGO_BOX = (1058, 16, 1272, 82)

# Umbral y dilatacion de la mascara. Valores mas ajustados dejan reaparecer un
# fantasma del texto sobre negro: el h264 reparte tinta un par de pixeles mas
# alla del trazo.
MASK_ALPHA = 0.05
MASK_DILATE = 2
MASK_SMOOTH = 2

OUT_DIR = os.path.join(PROJECT, "assets", "frames")

# Fuera del proyecto a proposito: si el proyecto vive en OneDrive, el
# sincronizador bloquea la carpeta y rmtree falla con "Acceso denegado".
TMP_DIR = os.path.join(tempfile.gettempdir(), "rotor-frames")


def ffmpeg_exe():
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        exe = shutil.which("ffmpeg")
        if not exe:
            sys.exit("Falta ffmpeg. Instala: pip install imageio-ffmpeg")
        return exe


def extract_raw():
    """Vuelca el tramo util del vídeo a PNG sin tocar nada mas."""
    if os.path.isdir(TMP_DIR):
        shutil.rmtree(TMP_DIR)
    os.makedirs(TMP_DIR)

    subprocess.run(
        [
            ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
            "-ss", str(START_SECONDS),
            "-i", SOURCE_VIDEO,
            "-start_number", "0",
            os.path.join(TMP_DIR, "%04d.png"),
            "-y",
        ],
        check=True,
    )
    names = sorted(f for f in os.listdir(TMP_DIR) if f.endswith(".png"))
    if not names:
        sys.exit("ffmpeg no extrajo ningun fotograma.")
    print("  fotogramas extraidos: %d" % len(names))
    return names


def watermark_mask(names):
    """Mascara de la marca de agua, estimada con el minimo temporal."""
    x0, y0, x1, y1 = LOGO_BOX
    acc = None
    for n in names:
        arr = np.asarray(
            Image.open(os.path.join(TMP_DIR, n)).convert("RGB").crop(LOGO_BOX),
            dtype=np.float32,
        )
        acc = arr if acc is None else np.minimum(acc, arr)
    alpha = (acc / 255.0).max(axis=2)
    mask = dilate(alpha > MASK_ALPHA, MASK_DILATE)
    print("  mascara de la marca: %.1f%% de la caja" % (mask.mean() * 100))
    return mask


def dilate(mask, radius):
    out = mask.copy()
    for _ in range(radius):
        p = np.pad(out, 1, mode="edge")
        out = p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:] | out
    return out


def _fill_columns(region, mask):
    """Interpola cada hueco de la mascara entre los vecinos conocidos de arriba
    y de abajo. Devuelve el relleno y el tamano del hueco por pixel."""
    h, w, _ = region.shape
    out = region.copy()
    gap = np.full((h, w), 1e6, np.float32)
    for x in range(w):
        col = mask[:, x]
        y = 0
        while y < h:
            if not col[y]:
                y += 1
                continue
            y0 = y
            while y < h and col[y]:
                y += 1
            y1 = y - 1
            top = region[y0 - 1, x] if y0 > 0 else None
            bottom = region[y1 + 1, x] if y1 < h - 1 else None
            if top is None and bottom is None:
                continue
            if top is None:
                top = bottom
            if bottom is None:
                bottom = top
            n = y1 - y0 + 1
            for k in range(n):
                t = (k + 1) / (n + 1)
                out[y0 + k, x] = top * (1 - t) + bottom * t
            gap[y0 : y1 + 1, x] = n
    return out, gap


def clean_frame(img, mask):
    """Devuelve el fotograma sin marca de agua."""
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    x0, y0, x1, y1 = LOGO_BOX
    region = arr[y0:y1, x0:x1].copy()

    vert, gap_v = _fill_columns(region, mask)
    horz, gap_h = _fill_columns(region.transpose(1, 0, 2), mask.T)
    horz, gap_h = horz.transpose(1, 0, 2), gap_h.T

    # Mezcla ponderada: manda la direccion cuyo hueco es mas corto.
    wv = (1.0 / gap_v)[..., None]
    wh = (1.0 / gap_h)[..., None]
    filled = np.where(mask[..., None], (vert * wv + horz * wh) / (wv + wh), region)

    # Suaviza solo la costura, sin tocar lo que ya era bueno.
    for _ in range(MASK_SMOOTH):
        p = np.pad(filled, ((1, 1), (1, 1), (0, 0)), mode="edge")
        neigh = (
            p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:] + 4 * filled
        ) / 8.0
        filled = np.where(mask[..., None], neigh, filled)

    arr[y0:y1, x0:x1] = np.clip(filled, 0, 255)
    return Image.fromarray(arr.astype("uint8"), "RGB")


def main():
    if not os.path.isfile(SOURCE_VIDEO):
        sys.exit("No encuentro el vídeo de origen: %s" % SOURCE_VIDEO)

    print("1/4  Extrayendo fotogramas del vídeo...")
    names = extract_raw()

    print("2/4  Estimando la marca de agua...")
    mask = watermark_mask(names)

    print("3/4  Remuestreando a %d fotogramas..." % FRAME_COUNT)
    picks = [
        names[round(i * (len(names) - 1) / (FRAME_COUNT - 1))]
        for i in range(FRAME_COUNT)
    ]

    # Se escribe fuera del proyecto y luego se mueve de golpe. Escribir 200
    # ficheros seguidos dentro de una carpeta de OneDrive hace que el
    # sincronizador cree copias en conflicto ("005-equipo.webp") a media
    # escritura.
    stage = os.path.join(tempfile.gettempdir(), "rotor-frames-out")
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    for sub, width, quality in SIZES:
        os.makedirs(os.path.join(stage, sub), exist_ok=True)

    print("4/4  Limpiando y exportando WebP...")
    for i, name in enumerate(picks):
        img = clean_frame(Image.open(os.path.join(TMP_DIR, name)), mask)
        for sub, width, quality in SIZES:
            h = round(img.height * width / img.width)
            h -= h % 2
            small = img.resize((width, h), Image.LANCZOS)
            small.save(
                os.path.join(stage, sub, "%03d.webp" % i),
                "WEBP",
                quality=quality,
                method=6,
            )
        if (i + 1) % 20 == 0 or i == len(picks) - 1:
            print("     %d/%d" % (i + 1, len(picks)))

    # Poster: el primer fotograma, para pintar algo antes de que cargue la
    # secuencia y para las etiquetas Open Graph.
    poster = clean_frame(Image.open(os.path.join(TMP_DIR, picks[0])), mask)
    poster.resize((1200, round(poster.height * 1200 / poster.width)), Image.LANCZOS).save(
        os.path.join(PROJECT, "assets", "img", "poster-despiece.webp"),
        "WEBP", quality=84, method=6,
    )
    # Imagen social 1200x630, recortada del fotograma intermedio.
    mid = clean_frame(Image.open(os.path.join(TMP_DIR, picks[len(picks) // 2])), mask)
    mid = mid.resize((1200, round(mid.height * 1200 / mid.width)), Image.LANCZOS)
    top = max(0, (mid.height - 630) // 2)
    mid.crop((0, top, 1200, top + 630)).save(
        os.path.join(PROJECT, "assets", "img", "og-cover.webp"),
        "WEBP", quality=84, method=6,
    )

    for sub, _, _ in SIZES:
        dest = os.path.join(OUT_DIR, sub)
        if os.path.isdir(dest):
            shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    for sub, _, _ in SIZES:
        shutil.move(os.path.join(stage, sub), os.path.join(OUT_DIR, sub))
    shutil.rmtree(stage, ignore_errors=True)
    shutil.rmtree(TMP_DIR, ignore_errors=True)

    for sub, width, _ in SIZES:
        d = os.path.join(OUT_DIR, sub)
        total = sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d))
        print(
            "  %s/  %d archivos  %5.1f KB de media  %5.2f MB total  (%dpx)"
            % (
                sub,
                len(os.listdir(d)),
                total / len(os.listdir(d)) / 1024,
                total / 1024 / 1024,
                width,
            )
        )
    print("Listo.")


if __name__ == "__main__":
    main()
