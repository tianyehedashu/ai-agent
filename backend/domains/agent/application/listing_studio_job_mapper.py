"""Listing Studio Job ORM → API dict 映射。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from domains.agent.infrastructure.models.listing_studio_job import ListingStudioJob


def job_to_dict(job: ListingStudioJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "user_id": str(job.user_id) if job.user_id else None,
        "anonymous_user_id": job.anonymous_user_id,
        "session_id": str(job.session_id) if job.session_id else None,
        "title": job.title,
        "status": job.status,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def job_to_dict_with_steps(job: ListingStudioJob) -> dict[str, Any]:
    d = job_to_dict(job)
    d["steps"] = [
        {
            "id": str(s.id),
            "job_id": str(s.job_id),
            "sort_order": s.sort_order,
            "capability_id": s.capability_id,
            "input_snapshot": s.input_snapshot,
            "output_snapshot": s.output_snapshot,
            "meta_prompt": s.meta_prompt,
            "generated_prompt": s.generated_prompt,
            "prompt_used": s.prompt_used,
            "prompt_template_id": str(s.prompt_template_id) if s.prompt_template_id else None,
            "status": s.status,
            "error_message": s.error_message,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in sorted(job.steps, key=lambda x: x.sort_order)
    ]
    return d


__all__ = ["job_to_dict", "job_to_dict_with_steps"]
