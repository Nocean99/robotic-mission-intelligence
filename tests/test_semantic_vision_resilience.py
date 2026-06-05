from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import autonomy.semantic_vision as semantic_vision
from autonomy.semantic_vision import OpenAIVisionLanguageScorer


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps({"output_text": "{\"score\":0.5,\"decision\":\"POSSIBLE_MATCH\",\"explanation\":\"ok\",\"tags\":[],\"needs_human_review\":true}"}).encode("utf-8")


def test_openai_scorer_retries_transient_http_error() -> None:
    calls = {"count": 0}
    previous_urlopen = semantic_vision.urlrequest.urlopen
    previous_sleep = semantic_vision.time.sleep

    def fake_urlopen(req, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise HTTPError(req.full_url, 503, "Service Unavailable", hdrs=None, fp=None)
        return FakeResponse()

    try:
        semantic_vision.urlrequest.urlopen = fake_urlopen
        semantic_vision.time.sleep = lambda seconds: None
        scorer = OpenAIVisionLanguageScorer(
            model="test-model",
            api_key="test-key",
            max_retries=2,
        )
        payload = scorer._open_with_retries(
            semantic_vision.urlrequest.Request(
                "https://api.openai.com/v1/responses",
                data=b"{}",
                method="POST",
            )
        )
    finally:
        semantic_vision.urlrequest.urlopen = previous_urlopen
        semantic_vision.time.sleep = previous_sleep

    assert calls["count"] == 2
    assert payload["output_text"]


if __name__ == "__main__":
    tests = [test_openai_scorer_retries_transient_http_error]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
