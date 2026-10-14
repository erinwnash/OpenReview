"""
OpenReview Python SDK.
Public interface for external automation, scripting, and DCC pipeline integration.
"""
from openreview.sdk.client import OpenReviewClient, OpenReviewError
from openreview.sdk.dcc import review_in_openreview

__all__ = ["OpenReviewClient", "OpenReviewError", "review_in_openreview"]
