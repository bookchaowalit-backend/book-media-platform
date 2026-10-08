---
title: Book Media Platform — Product Card
doc_id: CARD-book-media-platform
doc_type: product-card
verdict: merge
version: 0.1
date: 2026-10-08
status: ร่างเพื่อพิจารณา
owner: Product owner (Book Dev)
---

# Book Media Platform — Product Card

## 1. สรุปคุณค่าในหนึ่งประโยค

pipeline ในเครื่องที่แปลง job JSON/CSV เป็นกราฟิก SVG แก้ไขได้และ PNG (quote card, product card, announcement) ใน 3 ขนาด โดยไม่เรียก model

## 2. ปัญหาและผู้ใช้เป้าหมาย

- ปัญหา: ผลิตกราฟิกโซเชียลจำนวนมากจากข้อมูลโดยไม่ต้องออกแบบทีละชิ้นและไม่มีค่า model (`model_calls=0`)
- ผู้ใช้เป้าหมาย: เจ้าของและงานบริการสร้างสรรค์ใน Solo Empire **[สมมติฐาน]**

## 3. สิ่งที่ทำได้จริงตอนนี้

- `book_media_platform/graphics/` (cli, inputs, templates, svg, renderer, qa, service, benchmark) รับ `graphics.job.v1` แบบ inline, JSON หรือ CSV
- 3 template × 3 ขนาด (1080×1080, 1080×1350, 1080×1920); ตัดคำตาม grapheme และปฏิเสธข้อความที่ไม่พอดีโดยไม่สร้างผลลัพธ์บางส่วน
- จำกัด asset ให้อยู่ใต้ `assets_root`, รับเฉพาะ PNG/JPEG; rasterize ด้วย Edge headless แบบไม่มี network
- job lock พร้อม heartbeat และการ reclaim lock ที่ค้าง; golden PNG 9 ภาพใน `tests/golden/graphics-v1a/`
- ส่วน media อื่น (signed upload, metadata, object storage) ยังเป็น scaffold

## 4. หลักฐานสถานะ

- Stack: Python 3.11, Microsoft Edge headless (rasterize), `unittest`, GitHub Actions
- Commits: 11 (แรก 2026-09-17 / ล่าสุด 2026-10-01), branch `main`
- Source: 22 ไฟล์ / 4068 บรรทัด; test files: 16
- CI workflows: 1; deploy config: ไม่มี
- Live URL: ไม่มี
- README: 85 บรรทัด ("book-media-platform"); template family size: 1

## 5. คุณค่าและจุดต่าง

- deterministic, ปลอดภัยต่อ input และตรวจได้ด้วย golden test
- แต่ `catalog/production-tools.yaml` ระบุ owning repo ของ `graphics-v1a` เป็น `bookchaowalit/book-production-platform` (`book-production graphics batch`) ซึ่งพัฒนาต่อไปถึง V1B แล้ว
- **[สมมติฐาน]** มุมรายได้ (บริการทำกราฟิกจำนวนมาก) เป็นของ canonical repo ไม่ใช่ repo นี้

## 6. ช่องว่างสำคัญ

- ความสามารถซ้ำกับ `book-production-platform` และไม่มีใน production-tools catalog ในนามของ repo นี้
- ต้องพึ่ง Microsoft Edge ที่ติดตั้งในเครื่อง
- ไม่มี deploy และส่วน media หลักยังไม่เริ่ม

## 7. คำตัดสิน

**merge** → canonical: `bookchaowalit/book-production-platform` (graphics_production) Graphics V1A ที่นี่เป็นรุ่นก่อนหน้าของเครื่องมือที่ catalog รับรองแล้ว เงื่อนไขที่จะเปลี่ยนคำตัดสิน: ถ้าเริ่มทำ media platform จริง (upload/storage) ให้ repo นี้เหลือเฉพาะส่วนนั้นเป็น `template`

## 8. ขั้นต่อไป

1. เทียบ lock/heartbeat และ golden test กับ `graphics_production` แล้ว port ส่วนที่ canonical ยังไม่มี
2. ลบหรือทำเครื่องหมาย deprecated ให้ `book_media_platform/graphics` และอัปเดต `repository-catalog/roadmaps/platforms-backend.yaml`

## การอนุมัติ

| บทบาท | การตัดสินใจ | วันที่ |
|---|---|---|
| Product owner (Book Dev) | [ต้องยืนยัน] verdict `merge` | — |

## แหล่งข้อมูล

- `bookchaowalit-backend/book-backend/book-media-platform/README.md`
- `bookchaowalit-backend/book-backend/book-media-platform/docs/graphics-v1a.md`
- `bookchaowalit-backend/book-backend/book-media-platform/book_media_platform/graphics/`
- `catalog/production-tools.yaml`
- `repository-catalog/roadmaps/platforms-backend.yaml`
