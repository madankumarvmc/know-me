# Copyright (c) 2025, Meridian Mind and contributors
# For license information, please see license.txt

import frappe


def validate_cors_for_knowme():
	"""before_request hook: validates CORS origin against tenant's allowed_domains.

	- Only runs for knowme API paths (exits immediately for all other paths)
	- OPTIONS preflight requests are always allowed (token not available in preflight)
	- If allowed_domains is blank/empty, all origins are allowed (backwards compatible)
	- If allowed_domains is set, only those origins can use the API
	"""
	path = frappe.request.path or ""

	# Only intercept knowme API calls
	if "knowme.api." not in path:
		return

	# Always allow preflight requests
	if frappe.request.method == "OPTIONS":
		return

	# Extract origin
	origin = frappe.request.headers.get("Origin", "")
	if not origin:
		return  # Non-browser requests (curl, server-to-server) have no Origin

	# Get token from header or query params
	token = frappe.request.headers.get("X-KnowMe-Token", "")
	if not token:
		token = frappe.request.args.get("token", "")

	if not token:
		return  # Let the endpoint handler deal with missing tokens

	# Lookup tenant config
	configs = frappe.get_all(
		"KnowMe Config",
		filters={"api_token": token, "enabled": 1},
		fields=["name", "allowed_domains"],
		limit=1,
		ignore_permissions=True,
	)

	if not configs:
		return  # Let the endpoint handler deal with invalid tokens

	allowed_domains = configs[0].get("allowed_domains", "")
	if not allowed_domains or not allowed_domains.strip():
		return  # No restriction — allow all origins

	# Parse comma-separated allowed domains
	allowed_list = [d.strip().rstrip("/") for d in allowed_domains.split(",") if d.strip()]

	# Normalize origin (remove trailing slash)
	origin_normalized = origin.rstrip("/")

	if origin_normalized not in allowed_list:
		frappe.throw(
			f"Origin {origin} is not allowed for this API token",
			frappe.PermissionError,
		)
