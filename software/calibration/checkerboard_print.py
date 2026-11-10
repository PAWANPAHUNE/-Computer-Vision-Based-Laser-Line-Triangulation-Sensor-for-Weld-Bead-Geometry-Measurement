"""Printable checkerboard (vector PDF and SVG) with exact millimetre square size.

The board has (inner_corners_cols + 1) x (inner_corners_rows + 1) squares. A white border of at
least one square surrounds it (needed by the corner detector and for the laser-plane margin).
A 100 mm check bar is printed when it fits ("full" layout); otherwise ("compact") the label tells
the user how many squares must measure how many millimetres.
"""
from __future__ import annotations

from calibration.checkerboard import CheckerboardSpec

PAGE_SIZES_MM = {"A4": (297.0, 210.0), "A3": (420.0, 297.0), "Letter": (279.4, 215.9)}
PT_PER_MM = 72.0 / 25.4
MIN_BORDER_MM = 10.0
TEXT_BAND_MM = 22.0


COMPACT_BORDER_MM = 12.0


def layout(spec: CheckerboardSpec, page: str | None = None) -> dict:
    """Try A4 (then A3): 'full' layout with text band and 100 mm bar, else 'compact' (board centred,
    one text line, scale checked by measuring squares)."""
    cols, rows = spec.squares
    bw, bh = cols * spec.square_size_mm, rows * spec.square_size_mm
    border = max(MIN_BORDER_MM, spec.square_size_mm)
    order = [page] if page else ["A4", "A3"]
    for name in order:
        pw, ph = PAGE_SIZES_MM[name]
        if bw + 2 * border <= pw and bh + 2 * border + TEXT_BAND_MM <= ph:
            return {"page": name, "page_w": pw, "page_h": ph, "x0": (pw - bw) / 2, "y0": border,
                    "board_w": bw, "board_h": bh, "mode": "full"}
        if bw + 2 * COMPACT_BORDER_MM <= pw and bh + 2 * COMPACT_BORDER_MM <= ph:
            return {"page": name, "page_w": pw, "page_h": ph, "x0": (pw - bw) / 2, "y0": (ph - bh) / 2,
                    "board_w": bw, "board_h": bh, "mode": "compact"}
    raise ValueError(f"A {bw:.0f} x {bh:.0f} mm board does not fit on {'/'.join(order)} with margins. "
                     "Use smaller squares or fewer corners.")


def check_squares(spec: CheckerboardSpec) -> int:
    return min(4, spec.squares[0])


def _label(spec: CheckerboardSpec, compact: bool = False) -> list[str]:
    cols, rows = spec.squares
    if compact:
        n = check_squares(spec)
        return [f"Inner corners {spec.inner_corners_cols} x {spec.inner_corners_rows} | squares {cols} x {rows} | "
                f"square {spec.square_size_mm:g} mm | PRINT AT 100% (no Fit to page) | CHECK: {n} squares = "
                f"{n * spec.square_size_mm:g} mm"]
    return [f"Inner corners: {spec.inner_corners_cols} x {spec.inner_corners_rows}   Squares: {cols} x {rows}   "
            f"Square size: {spec.square_size_mm:g} mm",
            "PRINT AT 100% / ACTUAL SIZE. Turn OFF 'Fit to page'. Check: the bar below must measure exactly 100 mm."]


def _bar_mm(lay: dict) -> float:
    return 100.0 if lay["page_w"] - 40 >= 100 else 50.0


def checkerboard_svg(spec: CheckerboardSpec, page: str | None = None) -> str:
    lay = layout(spec, page)
    pw, ph, s = lay["page_w"], lay["page_h"], spec.square_size_mm
    cols, rows = spec.squares
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{pw}mm" height="{ph}mm" viewBox="0 0 {pw} {ph}">',
             f'<rect x="0" y="0" width="{pw}" height="{ph}" fill="white"/>']
    for r in range(rows):
        for c in range(cols):
            if (r + c) % 2 == 0:
                parts.append(f'<rect x="{lay["x0"] + c * s:.4f}" y="{lay["y0"] + r * s:.4f}" width="{s:.4f}" '
                             f'height="{s:.4f}" fill="black"/>')
    ty = lay["y0"] + lay["board_h"] + 6
    if lay["mode"] == "compact":
        parts.append(f'<text x="{lay["x0"]:.2f}" y="{ty:.2f}" font-family="Helvetica" font-size="2.8">'
                     f'{_label(spec, True)[0]}</text>')
        parts.append("</svg>")
        return "\n".join(parts)
    for i, line in enumerate(_label(spec)):
        parts.append(f'<text x="{lay["x0"]:.2f}" y="{ty + i * 4.5:.2f}" font-family="Helvetica" font-size="3.2">{line}</text>')
    bar = _bar_mm(lay)
    by = ty + 10
    parts.append(f'<rect x="{lay["x0"]:.2f}" y="{by:.2f}" width="{bar}" height="1.2" fill="black"/>')
    for k in range(0, int(bar) + 1, 10):
        parts.append(f'<rect x="{lay["x0"] + k - 0.15:.2f}" y="{by - 2:.2f}" width="0.3" height="3.2" fill="black"/>')
    parts.append(f'<text x="{lay["x0"] + bar + 2:.2f}" y="{by + 1.5:.2f}" font-family="Helvetica" font-size="3.2">'
                 f'{bar:g} mm</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def checkerboard_pdf(spec: CheckerboardSpec, page: str | None = None) -> bytes:
    """Single-page vector PDF. Coordinates are converted from mm to PDF points exactly."""
    lay = layout(spec, page)
    pw, ph, s = lay["page_w"], lay["page_h"], spec.square_size_mm
    cols, rows = spec.squares
    k = PT_PER_MM

    def y_pdf(y_top_mm: float, height_mm: float = 0.0) -> float:
        return (ph - y_top_mm - height_mm) * k

    ops = ["0 g"]
    for r in range(rows):
        for c in range(cols):
            if (r + c) % 2 == 0:
                ops.append(f"{(lay['x0'] + c * s) * k:.4f} {y_pdf(lay['y0'] + r * s, s):.4f} {s * k:.4f} {s * k:.4f} re f")
    ty = lay["y0"] + lay["board_h"] + 6
    if lay["mode"] == "compact":
        ops.append(f"BT /F1 8 Tf {lay['x0'] * k:.2f} {y_pdf(ty):.2f} Td ({_pdf_escape(_label(spec, True)[0])}) Tj ET")
    else:
        for i, line in enumerate(_label(spec)):
            ops.append(f"BT /F1 9 Tf {lay['x0'] * k:.2f} {y_pdf(ty + i * 4.5):.2f} Td ({_pdf_escape(line)}) Tj ET")
    bar = _bar_mm(lay) if lay["mode"] == "full" else 0.0
    by = ty + 10
    if bar:
        ops.append(f"{lay['x0'] * k:.4f} {y_pdf(by, 1.2):.4f} {bar * k:.4f} {1.2 * k:.4f} re f")
        for t in range(0, int(bar) + 1, 10):
            ops.append(f"{(lay['x0'] + t - 0.15) * k:.4f} {y_pdf(by - 2, 3.2):.4f} {0.3 * k:.4f} {3.2 * k:.4f} re f")
        ops.append(f"BT /F1 9 Tf {(lay['x0'] + bar + 2) * k:.2f} {y_pdf(by + 1.5):.2f} Td ({bar:g} mm) Tj ET")
    content = "\n".join(ops).encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {pw * k:.4f} {ph * k:.4f}] /Contents 4 0 R "
        f"/Resources << /Font << /F1 5 0 R >> >> >>".encode(),
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
