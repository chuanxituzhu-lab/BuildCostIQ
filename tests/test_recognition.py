from __future__ import annotations

import io
import unittest

from pypdf import PdfWriter

from adapters.recognition import recognize_source


class RecognitionTests(unittest.TestCase):
    def test_text_is_recognized_and_classified_locally(self):
        result, artifact = recognize_source(
            "contract-notes.txt",
            "合同清单包含工程量和单价，等待结算核对。".encode("utf-8"),
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["mode"], "local")
        self.assertIn(result["category"], {"清单与计价", "合同与商务", "结算与审计"})
        self.assertTrue(artifact.startswith(b"# contract-notes"))

    def test_pdf_without_text_is_held_for_ocr(self):
        output = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.write(output)
        result, artifact = recognize_source("drawing-scan.pdf", output.getvalue())
        self.assertEqual(result["status"], "needs_ocr")
        self.assertEqual(result["mode"], "local")
        self.assertIsNone(artifact)

    def test_external_ocr_requires_explicit_consent(self):
        result, artifact = recognize_source("site-photo.jpg", b"not-an-image", "baidu-ocr")
        self.assertEqual(result["status"], "consent_required")
        self.assertEqual(result["mode"], "external")
        self.assertIsNone(artifact)


if __name__ == "__main__":
    unittest.main()
