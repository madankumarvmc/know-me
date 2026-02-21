app_name = "knowme"
app_title = "KnowMe"
app_publisher = "Meridian Mind"
app_description = "AI Agentic Conversational Widget"
app_email = "contact@meridianmind.in"
app_license = "mit"

# Request Events
# ----------------
before_request = ["knowme.api.cors.validate_cors_for_knowme"]

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		"0 0 1 * *": [
			"knowme.api.scheduled_tasks.reset_monthly_quotas"
		],
	},
}
