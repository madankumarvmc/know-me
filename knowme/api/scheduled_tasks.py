# Copyright (c) 2025, Meridian Mind and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import today


def reset_monthly_quotas():
	"""Reset monthly usage counters for all tenants.

	Runs on the 1st of each month via Frappe scheduler.
	Sets current_month_usage to 0 and updates quota_reset_date.
	"""
	frappe.db.sql(
		"""UPDATE `tabKnowMe Config`
		SET current_month_usage = 0, quota_reset_date = %s
		WHERE enabled = 1""",
		(today(),),
	)
	frappe.db.commit()

	frappe.logger("knowme").info("Monthly usage quotas reset for all tenants")
