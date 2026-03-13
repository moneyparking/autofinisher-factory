from __future__ import annotations

import argparse
from pathlib import Path

from common import OUTPUTS_DIR

try:
    from pypdf import PdfWriter  # type: ignore
except Exception:  # pragma: no cover
    PdfWriter = None

try:
    from PyPDF2 import PdfMerger  # type: ignore
except Exception:  # pragma: no cover
    PdfMerger = None


def ordered_pdf_files(pages_dir: Path) -> list[Path]:
    if not pages_dir.exists():
        raise FileNotFoundError(f"Pages directory not found: {pages_dir}")
    pdfs = sorted(path for path in pages_dir.iterdir() if path.suffix.lower() == ".pdf")
    if not pdfs:
        raise FileNotFoundError(f"No PDF pages found in: {pages_dir}")
    return pdfs


def merge_with_pypdf(input_files: list[Path], output_file: Path) -> None:
    if PdfWriter is None:
        raise RuntimeError("pypdf is not available")
    writer = PdfWriter()
    for pdf_path in input_files:
        writer.append(str(pdf_path))
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("wb") as fh:
        writer.write(fh)


def merge_with_pypdf2(input_files: list[Path], output_file: Path) -> None:
    if PdfMerger is None:
        raise RuntimeError("PyPDF2 is not available")
    merger = PdfMerger()
    try:
        for pdf_path in input_files:
            merger.append(str(pdf_path))
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("wb") as fh:
            merger.write(fh)
    finally:
        merger.close()


def merge_pdfs(input_files: list[Path], output_file: Path) -> None:
    errors: list[str] = []
    for strategy in (merge_with_pypdf, merge_with_pypdf2):
        try:
            strategy(input_files, output_file)
            return
        except Exception as exc:  # pragma: no cover
            errors.append(f"{strategy.__name__}: {exc}")
    raise RuntimeError("No PDF merge backend succeeded. " + " | ".join(errors))


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge page-level PDFs into a single deliverable.pdf")
    parser.add_argument("product_slug", help="Product slug under outputs/")
    parser.add_argument(
        "--pages-dir",
        help="Optional explicit pages directory. Defaults to outputs/<slug>/pages",
    )
    parser.add_argument(
        "--output",
        help="Optional explicit output file path. Defaults to outputs/<slug>/deliverable.pdf",
    )
    args = parser.parse_args()

    product_dir = OUTPUTS_DIR / args.product_slug
    pages_dir = Path(args.pages_dir) if args.pages_dir else product_dir / "pages"
    output_file = Path(args.output) if args.output else product_dir / "deliverable.pdf"

    pdf_files = ordered_pdf_files(pages_dir)
    merge_pdfs(pdf_files, output_file)

    print(output_file)


if __name__ == "__main__":
    main()
