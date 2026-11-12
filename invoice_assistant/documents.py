"""Decode invoices, extract PDF text and run optional local OCR."""

import io
import json
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 5
MAX_PIXELS = 25_000_000


class DocumentError(ValueError):
    pass


@dataclass
class InvoiceDocument:
    name: str
    images: list[bytes]
    page_texts: list[str]

    @property
    def text(self):
        return "\n\n".join(self.page_texts)


def png_bytes(image: Image.Image) -> bytes:
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((2200, 2200))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def read_document(name: str, data: bytes) -> InvoiceDocument:
    if not data or len(data) > MAX_BYTES:
        raise DocumentError("Choose a non-empty file no larger than 10 MB.")
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        if not data.lstrip().startswith(b"%PDF-"):
            raise DocumentError("This file is not a valid PDF.")
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise DocumentError("Password-protected PDFs are not supported. Upload an unlocked copy.")
            if not 1 <= len(reader.pages) <= MAX_PAGES:
                raise DocumentError(f"Use an invoice with 1–{MAX_PAGES} pages.")
            texts = [(page.extract_text() or "").strip() for page in reader.pages]
            images = []
            pdf = pdfium.PdfDocument(data)
            try:
                for index in range(len(pdf)):
                    page = pdf[index]
                    try:
                        width, height = page.get_size()
                        if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
                            raise DocumentError("PDF page dimensions are too large.")
                        scale = min(2.0, 2200 / max(width, height))
                        bitmap = page.render(scale=scale)
                        try:
                            images.append(png_bytes(bitmap.to_pil()))
                        finally:
                            bitmap.close()
                    finally:
                        page.close()
            finally:
                pdf.close()
            return InvoiceDocument(name, images, texts)
        except DocumentError:
            raise
        except Exception as error:
            raise DocumentError("The PDF could not be read. Try a different PDF or a PNG/JPEG image.") from error
    if suffix not in {".png", ".jpg", ".jpeg"}:
        raise DocumentError("Supported formats: PDF, PNG and JPEG.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > MAX_PIXELS:
                raise DocumentError("Image exceeds 25 megapixels. Resize it before uploading.")
            return InvoiceDocument(name, [png_bytes(image)], [""])
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise DocumentError("The image could not be decoded. Use a valid PNG or JPEG.") from error


def _mac_ocr(path: Path) -> str:
    source = ROOT / "scripts/ocr_macos.swift"
    cache = ROOT / ".cache"
    cache.mkdir(exist_ok=True)
    binary = cache / "invoice-ocr"
    swiftc = shutil.which("swiftc")
    if not swiftc:
        raise DocumentError("macOS OCR needs Apple's command-line tools, or install Tesseract for local OCR.")
    if not binary.exists() or binary.stat().st_mtime < source.stat().st_mtime:
        module_cache = cache / "swift-modules"
        module_cache.mkdir(exist_ok=True)
        env = {**os.environ, "CLANG_MODULE_CACHE_PATH": str(module_cache)}
        result = subprocess.run(
            [swiftc, "-module-cache-path", str(module_cache), str(source), "-o", str(binary)],
            capture_output=True, text=True, timeout=180, env=env,
        )
        if result.returncode:
            raise DocumentError("Native OCR could not compile. Check that macOS command-line tools are installed, or use AI vision/manual entry.")
    result = subprocess.run([str(binary), str(path)], capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise DocumentError("Native OCR could not read the image. Try a clearer image or AI vision.")
    observations = json.loads(result.stdout)
    # Group words/columns at similar vertical positions before reading left to right.
    rows = []
    for item in sorted(observations, key=lambda item: -item["y"]):
        row = next((row for row in rows if abs(row[0]["y"] - item["y"]) < 0.012), None)
        if row is None:
            rows.append([item])
        else:
            row.append(item)
    return "\n".join("  ".join(item["text"] for item in sorted(row, key=lambda item: item["x"])) for row in rows)


def ocr_image(data: bytes) -> str:
    with tempfile.TemporaryDirectory(prefix="invoice-ocr-") as temp:
        path = Path(temp) / "invoice.png"
        path.write_bytes(data)
        try:
            if platform.system() == "Darwin":
                try:
                    return _mac_ocr(path)
                except DocumentError:
                    if not shutil.which("tesseract"):
                        raise
            if shutil.which("tesseract"):
                result = subprocess.run(["tesseract", str(path), "stdout", "--psm", "6"], capture_output=True, text=True, timeout=60)
                if result.returncode:
                    raise DocumentError("Tesseract could not read the image.")
                return result.stdout.strip()
            raise DocumentError("Local image OCR needs Tesseract on this computer. Text PDFs, pasted text, manual entry and optional AI vision remain available.")
        except subprocess.TimeoutExpired as error:
            raise DocumentError("OCR timed out. Try a smaller image or AI vision.") from error


def local_text(document: InvoiceDocument) -> tuple[str, str]:
    parts, modes = [], set()
    for text, image in zip(document.page_texts, document.images):
        if len(text.strip()) >= 35:
            parts.append(text)
            modes.add("PDF text")
        else:
            parts.append(ocr_image(image))
            modes.add("local OCR")
    result = "\n\n".join(parts)
    if not result.strip():
        raise DocumentError("No readable text was found. Try a clearer document or enter the fields manually.")
    return result, " + ".join(sorted(modes))
