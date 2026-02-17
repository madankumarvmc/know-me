# Copyright (c) 2025, Meridian Mind and contributors
# For license information, please see license.txt

import json
import frappe


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_widget_config(**kwargs):
	"""GET /api/method/knowme.api.config.get_widget_config?token=...

	Returns tenant-specific widget configuration for dynamic branding.
	Called by widget.js on initialization.
	"""
	# Set CORS headers
	frappe.local.response.headers = frappe.local.response.headers or {}
	frappe.local.response.headers["Access-Control-Allow-Origin"] = "*"
	frappe.local.response.headers["Access-Control-Allow-Headers"] = "Content-Type"
	frappe.local.response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"

	if frappe.request.method == "OPTIONS":
		return {}

	token = kwargs.get("token", "") or frappe.request.args.get("token", "")
	if not token:
		frappe.throw("Missing API token", frappe.AuthenticationError)

	configs = frappe.get_all(
		"KnowMe Config",
		filters={"api_token": token, "enabled": 1},
		fields=[
			"name", "tenant_name", "accent_color", "greeting_message",
			"max_messages", "bot_name", "suggested_chips",
		],
		limit=1,
		ignore_permissions=True,
	)

	if not configs:
		frappe.throw("Invalid or disabled API token", frappe.AuthenticationError)

	config = configs[0]

	# Parse suggested chips (comma-separated string → array of chip objects)
	chips = []
	if config.get("suggested_chips"):
		chip_texts = [c.strip() for c in config["suggested_chips"].split(",") if c.strip()]
		for i, text in enumerate(chip_texts):
			chips.append({
				"id": f"init_chip_{i}",
				"text": text,
				"icon": "💬",
			})

	return {
		"tenantName": config.get("tenant_name", ""),
		"botName": config.get("bot_name", "") or config.get("tenant_name", "Know Me"),
		"accentColor": config.get("accent_color", "#FF6B6B"),
		"greetingMessage": config.get("greeting_message", "Hey there! I'm an AI assistant. What would you like to know?"),
		"maxMessages": config.get("max_messages", 18),
		"suggestedChips": chips,
	}
