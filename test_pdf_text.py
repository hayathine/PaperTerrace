#!/usr/bin/env python3
"""
PDFのテキスト抽出テスト

Usage:
    python test_pdf_text.py <pdf_file_path>
"""

import sys

import pdfplumber


def test_pdf(pdf_path):
    print(f"Testing PDF: {pdf_path}")
    print("=" * 80)

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"Total pages: {total_pages}\n")

        for i, page in enumerate(pdf.pages[:3]):  # Test first 3 pages
            page_num = i + 1
            print(f"Page {page_num}:")
            print("-" * 40)

            # Extract native words
            words = page.extract_words(use_text_flow=True, x_tolerance=1, y_tolerance=3)
            print(f"  Native words extracted: {len(words)}")

            if words:
                print(f"  Sample words: {[w['text'] for w in words[:5]]}")

            # Extract text
            text = page.extract_text()
            if text:
                print(f"  Text length: {len(text)}")
                print(f"  Sample text: {text[:100]}...")
            else:
                print("  WARNING: No text extracted! This might be a scanned PDF.")

            # Page dimensions
            print(f"  Page size: {page.width} x {page.height} points")

            print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_pdf_text.py <pdf_file_path>")
        sys.exit(1)

    test_pdf(sys.argv[1])
