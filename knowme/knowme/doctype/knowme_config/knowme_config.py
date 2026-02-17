# Copyright (c) 2025, Meridian Mind and contributors
# For license information, please see license.txt

import frappe
import secrets
from frappe.model.document import Document


class KnowMeConfig(Document):
	def before_insert(self):
		if not self.api_token:
			self.api_token = secrets.token_urlsafe(32)
