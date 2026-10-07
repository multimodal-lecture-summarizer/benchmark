#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from docx import Document
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

doc = Document('docs/workspace/NguyenNgocDuy_E14_updated.docx')

print("=" * 100)
print("NỘI DUNG DOCX - NguyenNgocDuy_E14_updated.docx")
print("=" * 100)

for idx, para in enumerate(doc.paragraphs):
    text = para.text.strip()
    if text:
        style = para.style.name if para.style else "Normal"
        print(f"[{idx:4d}|{style:20s}] {text[:120]}")

print("\n" + "=" * 100)
print("BẢNG TRONG DOCX")
print("=" * 100)

for tbl_idx, table in enumerate(doc.tables):
    print(f"\n--- BẢNG {tbl_idx + 1} ---")
    for row_idx, row in enumerate(table.rows):
        row_text = " | ".join([cell.text.strip()[:50] for cell in row.cells])
        print(f"[Hàng {row_idx + 1}] {row_text}")

print("\n" + "=" * 100)
print("CHI TIẾT BẢNG (đầy đủ)")
print("=" * 100)

for tbl_idx, table in enumerate(doc.tables):
    print(f"\n=== BẢNG {tbl_idx + 1} ===")
    for row_idx, row in enumerate(table.rows):
        print(f"\nHàng {row_idx + 1}:")
        for cell_idx, cell in enumerate(row.cells):
            cell_text = cell.text.strip()
            if cell_text:
                print(f"  [Cột {cell_idx + 1}] {cell_text}")
