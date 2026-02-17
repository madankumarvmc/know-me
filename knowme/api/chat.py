# Copyright (c) 2025, Meridian Mind and contributors
# For license information, please see license.txt

import json
import frappe
from .agent import run_agent


@frappe.whitelist(allow_guest=True)
def handle(**kwargs):
	"""POST /api/method/knowme.api.chat.handle

	Thin endpoint: validates token, checks rate limits, calls agent, returns result.

	Request body:
		message (str): The user's message
		sessionId (str): Client-generated session ID
		conversationHistory (list): Previous messages for context
		messageCount (int): Current message count in session
	"""
	# Set CORS headers for cross-origin widget requests
	frappe.local.response.headers = frappe.local.response.headers or {}
	frappe.local.response.headers["Access-Control-Allow-Origin"] = "*"
	frappe.local.response.headers["Access-Control-Allow-Headers"] = "X-KnowMe-Token, Content-Type"
	frappe.local.response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"

	# Handle preflight
	if frappe.request.method == "OPTIONS":
		return {}

	# 1. Validate API token
	token = frappe.request.headers.get("X-KnowMe-Token", "")
	if not token:
		frappe.throw("Missing API token", frappe.AuthenticationError)

	configs = frappe.get_all(
		"KnowMe Config",
		filters={"api_token": token, "enabled": 1},
		fields=["name"],
		limit=1,
		ignore_permissions=True,
	)

	if not configs:
		frappe.throw("Invalid or disabled API token", frappe.AuthenticationError)

	tenant_config = frappe.get_doc("KnowMe Config", configs[0].name)
	tenant_config.flags.ignore_permissions = True

	# 2. Rate limit check
	ip = frappe.request.remote_addr
	if _is_rate_limited(ip, tenant_config.name):
		return {
			"text": "You've been very curious! Come back in a bit and we can chat more. 😊",
			"chips": [],
			"cards": [],
			"meta": {"topic": "rate_limit", "isGoodbye": True, "remainingMessages": 0},
		}

	# 3. Usage quota check
	if _is_quota_exceeded(tenant_config):
		return {
			"text": "This assistant has reached its monthly usage limit. Please check back next month! 🙏",
			"chips": [],
			"cards": [],
			"meta": {"topic": "quota_exceeded", "isGoodbye": True, "remainingMessages": 0},
		}

	# 4. Parse request
	message = kwargs.get("message", "").strip()
	session_id = kwargs.get("sessionId", "anonymous")
	conversation_history = kwargs.get("conversationHistory", [])
	message_count = int(kwargs.get("messageCount", 0))

	if not message:
		frappe.throw("Message is required", frappe.ValidationError)

	# 5. Check session message limit
	max_messages = tenant_config.max_messages or 18
	remaining = max(0, max_messages - message_count)

	if remaining <= 0:
		return {
			"text": "We've had a wonderful conversation! Feel free to come back anytime for another chat. 👋",
			"chips": [],
			"cards": [],
			"meta": {"topic": "session_end", "isGoodbye": True, "remainingMessages": 0},
		}

	# 6. Run ADK agent
	try:
		result = run_agent(tenant_config, message, session_id, conversation_history)
	except Exception as e:
		import traceback
		err_detail = traceback.format_exc()
		frappe.log_error(title="KnowMe Agent Error", message=err_detail)
		result = {
			"text": "I stumbled a bit there. Could you try asking again?",
			"chips": [
				{"id": "retry", "text": "Try again", "icon": "🔄"},
				{"id": "about", "text": "Tell me about yourself", "icon": "👤"},
			],
			"cards": [],
			"meta": {"topic": "error"},
		}

	# 7. Add remaining messages to meta
	result.setdefault("meta", {})
	result["meta"]["remainingMessages"] = remaining - 1
	result["meta"]["isGoodbye"] = False

	# Hint wrap-up when 3 messages remain
	if remaining <= 3:
		result["meta"]["wrapUp"] = True

	# 8. Increment usage quota (atomic SQL update)
	_increment_quota(tenant_config.name)

	# 9. Log session with conversation log
	frappe.enqueue(
		_log_chat_session,
		tenant=tenant_config.name,
		session_id=session_id,
		message_count=message_count + 1,
		ip=ip,
		user_message=message,
		assistant_response=result.get("text", ""),
		queue="short",
	)

	return result


def _is_rate_limited(ip, tenant_name):
	"""Check if IP has exceeded rate limit (10 sessions/hr)."""
	from datetime import datetime, timedelta

	one_hour_ago = datetime.now() - timedelta(hours=1)

	session_count = frappe.db.count(
		"Chat Session",
		filters={
			"tenant": tenant_name,
			"visitor_ip": ip,
			"started_at": [">=", one_hour_ago],
		},
	)

	return session_count >= 10


def _is_quota_exceeded(tenant_config):
	"""Check if tenant has exceeded monthly usage quota."""
	monthly_quota = tenant_config.monthly_quota or 0
	if monthly_quota <= 0:
		return False  # No quota set = unlimited

	current_usage = tenant_config.current_month_usage or 0
	return current_usage >= monthly_quota


def _increment_quota(tenant_name):
	"""Atomically increment the monthly usage counter."""
	frappe.db.sql(
		"""UPDATE `tabKnowMe Config`
		SET current_month_usage = COALESCE(current_month_usage, 0) + 1
		WHERE name = %s""",
		(tenant_name,),
	)


def _log_chat_session(tenant, session_id, message_count, ip, user_message="", assistant_response=""):
	"""Log or update chat session record with conversation log."""
	from datetime import datetime

	existing = frappe.db.exists(
		"Chat Session",
		{"tenant": tenant, "session_id": session_id},
	)

	if existing:
		# Load existing conversation log and append
		doc = frappe.get_doc("Chat Session", existing)
		doc.flags.ignore_permissions = True

		log = []
		if doc.conversation_log:
			try:
				log = json.loads(doc.conversation_log)
			except (json.JSONDecodeError, TypeError):
				log = []

		# Append user message and assistant response
		timestamp = datetime.now().isoformat()
		if user_message:
			log.append({"role": "user", "content": user_message, "timestamp": timestamp})
		if assistant_response:
			log.append({"role": "assistant", "content": assistant_response, "timestamp": timestamp})

		doc.message_count = message_count
		doc.conversation_log = json.dumps(log)
		doc.save(ignore_permissions=True)
	else:
		# Create new session with initial conversation log
		timestamp = datetime.now().isoformat()
		log = []
		if user_message:
			log.append({"role": "user", "content": user_message, "timestamp": timestamp})
		if assistant_response:
			log.append({"role": "assistant", "content": assistant_response, "timestamp": timestamp})

		doc = frappe.get_doc({
			"doctype": "Chat Session",
			"tenant": tenant,
			"session_id": session_id,
			"message_count": message_count,
			"visitor_ip": ip,
			"conversation_log": json.dumps(log),
		})
		doc.insert(ignore_permissions=True)

	frappe.db.commit()
