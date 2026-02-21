# Copyright (c) 2025, Meridian Mind and contributors
# For license information, please see license.txt

import os
import mimetypes

import frappe
from frappe.model.document import Document


ALLOWED_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif")


class KnowledgeEntry(Document):
	def validate(self):
		if self.uploaded_file:
			old_doc = self.get_doc_before_save()
			old_file = old_doc.uploaded_file if old_doc else None
			if self.uploaded_file != old_file:
				self._validate_file_type()
				self._extract_content()

	def _validate_file_type(self):
		file_ext = os.path.splitext(self.uploaded_file)[1].lower()
		if file_ext not in ALLOWED_EXTENSIONS:
			frappe.throw(
				f"Unsupported file type: {file_ext}. "
				f"Allowed: PDF, PNG, JPG, JPEG, WebP, BMP, TIFF",
				title="Invalid File Type",
			)

	def _extract_content(self):
		file_ext = os.path.splitext(self.uploaded_file)[1].lower()
		self.extraction_status = "Processing"
		self.extraction_log = ""

		try:
			file_path = self._get_physical_path()

			if file_ext == ".pdf":
				self.source_type = "PDF"
				extracted = self._extract_from_pdf(file_path)
			elif file_ext in IMAGE_EXTENSIONS:
				self.source_type = "Image"
				extracted = self._extract_from_image(file_path)
			else:
				frappe.throw(f"Unsupported file type: {file_ext}")
				return

			if extracted and extracted.strip():
				self.content = extracted.strip()
				self.extraction_status = "Completed"
				self.extraction_log = f"Extracted {len(self.content)} characters"
			else:
				self.extraction_status = "Failed"
				self.extraction_log = "Extraction returned empty content"
				frappe.msgprint(
					"Could not extract text from the uploaded file. "
					"Please enter content manually.",
					indicator="orange",
					title="Extraction Warning",
				)
		except frappe.ValidationError:
			raise
		except Exception as e:
			self.extraction_status = "Failed"
			self.extraction_log = str(e)[:500]
			frappe.log_error(
				title="KnowMe: Document Extraction Failed",
				message=(
					f"Knowledge Entry: {self.name or 'New'}\n"
					f"File: {self.uploaded_file}\n"
					f"Error: {str(e)}"
				),
			)
			frappe.msgprint(
				f"Document extraction failed: {str(e)[:200]}. "
				"You can still save with manually entered content.",
				indicator="red",
				title="Extraction Error",
			)

	def _get_physical_path(self):
		file_url = self.uploaded_file
		if file_url.startswith("/private/files/"):
			return frappe.get_site_path("private", "files", os.path.basename(file_url))
		elif file_url.startswith("/files/"):
			return frappe.get_site_path("public", "files", os.path.basename(file_url))
		else:
			frappe.throw(f"Unexpected file URL format: {file_url}")

	def _extract_from_pdf(self, file_path):
		import fitz  # PyMuPDF

		doc = fitz.open(file_path)
		text_parts = []
		pages_without_text = 0
		total_pages = len(doc)

		for page_num in range(total_pages):
			page = doc[page_num]
			text = page.get_text("text").strip()
			if text:
				text_parts.append(text)
			else:
				pages_without_text += 1

		doc.close()

		if total_pages == 0:
			return ""

		# If 70%+ pages have text, use PyMuPDF result
		if text_parts and pages_without_text <= (total_pages * 0.3):
			return "\n\n".join(text_parts)

		# Scanned PDF or mostly images — fall back to Gemini Vision
		self.extraction_log = (
			f"PDF has {pages_without_text}/{total_pages} pages without text. "
			"Falling back to Gemini Vision API."
		)
		return self._extract_with_gemini(file_path)

	def _extract_from_image(self, file_path):
		return self._extract_with_gemini(file_path)

	def _extract_with_gemini(self, file_path):
		from google import genai
		from google.genai import types

		api_key = self._get_tenant_api_key()
		if not api_key:
			frappe.throw(
				"No LLM API key found for this tenant. "
				"Please configure it in KnowMe Config.",
				title="Missing API Key",
			)

		client = genai.Client(api_key=api_key)

		with open(file_path, "rb") as f:
			file_bytes = f.read()

		mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

		prompt = (
			"Extract ALL text content from this document. "
			"Preserve the structure: headings, paragraphs, lists, tables. "
			"Return ONLY the extracted text, no commentary or markup. "
			"If there are tables, format them in a readable plain-text format. "
			"If the document contains both text and images with text, extract text from both."
		)

		response = client.models.generate_content(
			model="gemini-2.0-flash",
			contents=[
				types.Content(
					parts=[
						types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
						types.Part.from_text(text=prompt),
					]
				)
			],
		)

		return response.text

	def _get_tenant_api_key(self):
		if not self.tenant:
			return None
		return frappe.utils.password.get_decrypted_password(
			"KnowMe Config", self.tenant, "llm_api_key"
		)
