# Copyright (c) 2025, Meridian Mind and contributors
# For license information, please see license.txt

import frappe

# Module-level tenant (safe for gunicorn sync workers — one request per process)
_current_tenant = None


def _get_tenant():
	"""Get current tenant from module-level variable."""
	return _current_tenant


def set_tenant(tenant_name):
	"""Set current tenant for tool functions."""
	global _current_tenant
	_current_tenant = tenant_name


def search_blog_posts(query: str, category: str = "") -> dict:
	"""Search blog posts by keyword, tag, or category.
	Use when visitor asks about writing, blog content, or specific topics.

	Args:
		query: Search keyword to find in titles, content, and tags.
		category: Optional category filter.
	"""
	tenant = _get_tenant()
	if not tenant:
		return {"status": "error", "message": "No tenant configured"}

	filters = {"tenant": tenant}
	if category:
		filters["topic"] = category

	entries = frappe.get_all(
		"Knowledge Entry",
		filters=filters,
		or_filters=[
			["title", "like", f"%{query}%"],
			["content", "like", f"%{query}%"],
		],
		fields=["title", "content", "source_url", "topic"],
		limit=5,
	)
	return {"status": "success", "results": entries, "count": len(entries)}


def get_knowledge(topic: str) -> dict:
	"""Retrieve specific knowledge about me by topic.
	Use when visitor asks about background, skills, interests, or personality.

	Args:
		topic: One of: professional, personal, skills, interests, values, website, blog.
	"""
	tenant = _get_tenant()
	if not tenant:
		return {"status": "error", "message": "No tenant configured"}

	entries = frappe.get_all(
		"Knowledge Entry",
		filters={"tenant": tenant, "topic": topic},
		fields=["title", "content"],
	)
	return {"status": "success", "data": entries}


def get_blog_post_detail(title: str) -> dict:
	"""Get full content of a specific blog post for in-depth discussion.

	Args:
		title: The title or partial title of the blog post.
	"""
	tenant = _get_tenant()
	if not tenant:
		return {"status": "error", "message": "No tenant configured"}

	entries = frappe.get_all(
		"Knowledge Entry",
		filters={"tenant": tenant},
		or_filters=[["title", "like", f"%{title}%"]],
		fields=["title", "content", "source_url"],
		limit=1,
	)
	return {"status": "success", "post": entries[0] if entries else None}


def list_skills(domain: str = "all") -> dict:
	"""List skills filtered by domain.

	Args:
		domain: Filter by: technical, domains, tools, or all.
	"""
	tenant = _get_tenant()
	if not tenant:
		return {"status": "error", "message": "No tenant configured"}

	filters = {"tenant": tenant, "topic": "skills"}
	if domain != "all":
		filters["title"] = ["like", f"%{domain}%"]

	entries = frappe.get_all(
		"Knowledge Entry",
		filters=filters,
		fields=["title", "content"],
	)
	return {"status": "success", "skills": entries}


def suggest_related_content(topic: str) -> dict:
	"""Find content related to the current conversation topic.

	Args:
		topic: The topic to find related content for.
	"""
	tenant = _get_tenant()
	if not tenant:
		return {"status": "error", "message": "No tenant configured"}

	entries = frappe.get_all(
		"Knowledge Entry",
		filters={"tenant": tenant},
		or_filters=[
			["title", "like", f"%{topic}%"],
			["content", "like", f"%{topic}%"],
		],
		fields=["title", "content", "topic", "source_url"],
		limit=3,
	)
	return {"status": "success", "related": entries}
