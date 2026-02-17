# Copyright (c) 2025, Meridian Mind and contributors
# For license information, please see license.txt

import csv
import io
import frappe
from frappe.utils import now_datetime
from urllib.request import urlopen
from urllib.error import URLError


def run_pipeline():
	"""Ingest knowledge from Google Spreadsheet CSV into Knowledge Entries.

	Runs hourly via Frappe scheduler. For each enabled tenant with a
	knowledge_spreadsheet_url set, fetches the CSV, upserts Knowledge
	Entries by (tenant, topic, title), and optionally deletes orphans.

	Expected CSV columns: topic, title, content, source_url
	"""
	tenants = frappe.get_all(
		"KnowMe Config",
		filters={
			"enabled": 1,
			"knowledge_spreadsheet_url": ["is", "set"],
		},
		fields=["name", "knowledge_spreadsheet_url", "pipeline_delete_orphans"],
		ignore_permissions=True,
	)

	for tenant in tenants:
		try:
			_sync_tenant(tenant)
		except Exception:
			import traceback
			err = traceback.format_exc()
			frappe.log_error(
				title=f"KnowMe Pipeline Error: {tenant.name}",
				message=err,
			)
			frappe.db.set_value(
				"KnowMe Config", tenant.name,
				{
					"pipeline_sync_status": f"Error: {str(err)[:200]}",
					"last_pipeline_sync": now_datetime(),
				},
				update_modified=False,
			)
			frappe.db.commit()


def _sync_tenant(tenant):
	"""Sync knowledge entries for a single tenant from their spreadsheet."""
	url = tenant.knowledge_spreadsheet_url.strip()
	if not url:
		return

	# Fetch CSV content
	try:
		response = urlopen(url, timeout=30)
		content = response.read().decode("utf-8-sig")  # Handle BOM
	except (URLError, Exception) as e:
		raise Exception(f"Failed to fetch spreadsheet: {str(e)}")

	# Parse CSV
	reader = csv.DictReader(io.StringIO(content))

	# Normalize column names (lowercase, strip whitespace)
	rows = []
	for row in reader:
		normalized = {k.strip().lower(): v.strip() for k, v in row.items() if k}
		if normalized.get("topic") and normalized.get("title") and normalized.get("content"):
			rows.append(normalized)

	if not rows:
		raise Exception("No valid rows found in spreadsheet (need: topic, title, content columns)")

	# Track which entries we've seen (for orphan deletion)
	seen_keys = set()

	for row in rows:
		topic = row["topic"].strip()
		title = row["title"].strip()
		content = row["content"].strip()
		source_url = row.get("source_url", "").strip()

		entry_key = (tenant.name, topic, title)
		seen_keys.add(entry_key)

		# Upsert: find existing entry by tenant + topic + title
		existing = frappe.get_all(
			"Knowledge Entry",
			filters={
				"tenant": tenant.name,
				"topic": topic,
				"title": title,
			},
			fields=["name"],
			limit=1,
			ignore_permissions=True,
		)

		if existing:
			# Update existing entry
			doc = frappe.get_doc("Knowledge Entry", existing[0].name)
			doc.flags.ignore_permissions = True
			doc.content = content
			doc.source_url = source_url
			doc.last_processed = now_datetime()
			doc.save(ignore_permissions=True)
		else:
			# Create new entry
			doc = frappe.get_doc({
				"doctype": "Knowledge Entry",
				"tenant": tenant.name,
				"topic": topic,
				"title": title,
				"content": content,
				"source_url": source_url,
				"last_processed": now_datetime(),
			})
			doc.insert(ignore_permissions=True)

	# Optionally delete orphans (entries not in spreadsheet)
	if tenant.pipeline_delete_orphans:
		all_entries = frappe.get_all(
			"Knowledge Entry",
			filters={"tenant": tenant.name},
			fields=["name", "topic", "title"],
			ignore_permissions=True,
		)

		for entry in all_entries:
			key = (tenant.name, entry.topic, entry.title)
			if key not in seen_keys:
				frappe.delete_doc("Knowledge Entry", entry.name, ignore_permissions=True)

	# Update sync status
	frappe.db.set_value(
		"KnowMe Config", tenant.name,
		{
			"pipeline_sync_status": f"Success: {len(rows)} entries synced",
			"last_pipeline_sync": now_datetime(),
		},
		update_modified=False,
	)

	frappe.db.commit()
