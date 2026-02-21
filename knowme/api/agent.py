# Copyright (c) 2025, Meridian Mind and contributors
# For license information, please see license.txt

import asyncio
import json
import os
import frappe
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types as genai_types


def _fetch_knowledge(tenant_name):
	"""Pre-fetch all knowledge entries for the tenant (runs in Frappe's DB context)."""
	entries = frappe.get_all(
		"Knowledge Entry",
		filters={"tenant": tenant_name},
		fields=["topic", "title", "content", "source_url"],
		order_by="topic asc, title asc",
		ignore_permissions=True,
	)

	# Group by topic
	by_topic = {}
	for e in entries:
		topic = e.get("topic", "general")
		if topic not in by_topic:
			by_topic[topic] = []
		by_topic[topic].append(e)

	# Format as text for the prompt
	sections = []
	for topic, items in by_topic.items():
		section = f"\n## {topic.upper()}\n"
		for item in items:
			section += f"### {item['title']}\n{item['content']}\n"
			if item.get("source_url"):
				section += f"URL: {item['source_url']}\n"
		sections.append(section)

	return "\n".join(sections)


def create_agent(tenant_config, knowledge_text):
	"""Create an ADK agent for a specific tenant with pre-loaded knowledge."""
	persona = tenant_config.persona_prompt or "You are a helpful AI assistant."
	bot_name = tenant_config.bot_name or tenant_config.tenant_name

	instruction = f"""{persona}

Your name is {bot_name}.

KNOWLEDGE BASE — Use ONLY this data to answer questions. NEVER fabricate facts:
{knowledge_text}

RESPONSE FORMAT — respond ONLY with valid JSON (no markdown fences, no extra text):
{{
  "text": "Your response in 2-4 sentences. You can use <b>bold</b> and <i>italic</i> HTML.",
  "chips": [
    {{"id": "chip_1", "text": "Suggested question", "icon": "\U0001f4ac"}},
    {{"id": "chip_2", "text": "Another suggestion", "icon": "\u2728"}},
    {{"id": "chip_3", "text": "Third option", "icon": "\U0001f680"}}
  ],
  "cards": [],
  "meta": {{"topic": "current_topic"}}
}}

RULES:
- Answer ONLY from the KNOWLEDGE BASE above. If not found, say so honestly.
- Always provide 3-5 chips as conversation starters relevant to the knowledge base.
- Chip icons MUST be single Unicode emoji characters (e.g. \U0001f4ac \u2728 \U0001f680 \u270d\ufe0f \U0001f4a1 \U0001f3a8 \u2764\ufe0f \U0001f4bb), NEVER text words like "star" or "factory".
- Keep responses warm, engaging, and concise (2-4 sentences).
- Adapt tone: professional for career questions, warm for personal questions, enthusiastic for interests.
- When mentioning blog posts, include them as cards: {{"type": "blog_post", "title": "Post Title", "slug": "post-slug"}}
- Use <b>bold</b> for emphasis and <i>italic</i> for subtle highlights.
"""

	return Agent(
		name="knowme_agent",
		model=tenant_config.llm_model or "gemini-2.0-flash",
		description=f"AI assistant for {bot_name}",
		instruction=instruction,
		tools=[],  # No tools needed — knowledge is pre-loaded in instruction
	)


def parse_response(raw_text):
	"""Parse agent response JSON, with fallback for malformed responses."""
	if not raw_text:
		return {
			"text": "I'm having trouble responding right now. Please try again!",
			"chips": [{"id": "retry", "text": "Try again", "icon": "🔄"}],
			"cards": [],
			"meta": {"topic": "error"},
		}

	# Strip markdown code fences if present
	text = raw_text.strip()
	if text.startswith("```json"):
		text = text[7:]
	if text.startswith("```"):
		text = text[3:]
	if text.endswith("```"):
		text = text[:-3]
	text = text.strip()

	try:
		parsed = json.loads(text)
		# Ensure required fields exist
		if "text" not in parsed:
			parsed["text"] = text
		if "chips" not in parsed:
			parsed["chips"] = []
		if "cards" not in parsed:
			parsed["cards"] = []
		if "meta" not in parsed:
			parsed["meta"] = {}
		return parsed
	except json.JSONDecodeError:
		# LLM returned plain text instead of JSON
		return {
			"text": text,
			"chips": [
				{"id": "tell_more", "text": "Tell me more", "icon": "💬"},
				{"id": "skills", "text": "What are your skills?", "icon": "🛠️"},
				{"id": "blog", "text": "Show me your writing", "icon": "✍️"},
			],
			"cards": [],
			"meta": {"topic": "general"},
		}


def run_agent(tenant_config, user_message, session_id, conversation_history=None):
	"""Run agent and return structured response."""
	# Configure API key for Gemini
	api_key = tenant_config.get_password("llm_api_key")
	os.environ["GOOGLE_API_KEY"] = api_key

	# Pre-fetch all knowledge while we have Frappe's DB context
	knowledge_text = _fetch_knowledge(tenant_config.name)

	agent = create_agent(tenant_config, knowledge_text)
	runner = InMemoryRunner(agent=agent, app_name="knowme")

	# Build message with conversation context
	message_text = user_message
	if conversation_history:
		recent = conversation_history[-12:] if len(conversation_history) > 12 else conversation_history
		context_parts = []
		for msg in recent:
			role = msg.get("role", "user")
			content = msg.get("content", "")
			if role == "user":
				context_parts.append(f"Visitor: {content}")
			else:
				context_parts.append(f"You: {content}")
		context = "\n".join(context_parts)
		message_text = f"[Previous conversation for context]\n{context}\n\n[Current message]\n{user_message}"

	message = genai_types.Content(
		role="user",
		parts=[genai_types.Part(text=message_text)],
	)

	# Create session first (InMemoryRunner requires explicit session)
	async def _create_session():
		return await runner.session_service.create_session(
			app_name="knowme",
			user_id="visitor",
		)

	session = asyncio.run(_create_session())

	# runner.run() is a sync generator (internally uses threads + asyncio)
	final_text = ""
	for event in runner.run(
		user_id="visitor",
		session_id=session.id,
		new_message=message,
	):
		if event.is_final_response() and event.content and event.content.parts:
			final_text = event.content.parts[0].text

	return parse_response(final_text)
