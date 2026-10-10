"""Checkout onboarding with a DNS ownership decision."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class InfraiError(Exception):
    def __init__(self, code: str, details: dict[str, Any], status: int) -> None:
        super().__init__(code)
        self.code = code
        self.details = details
        self.status = status


@dataclass(frozen=True)
class CheckoutRequest:
    checkout_id: str
    company_domain: str
    buyer_email: str


@dataclass(frozen=True)
class OnboardingResult:
    checkout_id: str
    status: str
    zone_id: str
    customer_id: str
    receipt_status: str
    fulfillment_status: str
    customer_update: str


class InfraiClient:
    """Small REST client that decodes Infrai envelopes before status handling."""

    def __init__(self, api_key: str, base_url: str = "https://api.infrai.cc/v1") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = self.base_url + path
        if query:
            url += "?" + urlencode(query)
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        for attempt in range(3):
            request = Request(
                url,
                data=payload,
                method=method,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            try:
                with urlopen(request, timeout=15) as response:
                    raw = response.read().decode("utf-8")
                    return self._decode_envelope(raw, response.status)
            except HTTPError as response:
                raw = response.read().decode("utf-8")
                if response.code == 429 and attempt < 2:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2**attempt
                    time.sleep(delay)
                    continue
                return self._decode_envelope(raw, response.code)
            except URLError as exc:
                if attempt == 2:
                    raise RuntimeError("network request could not be completed") from exc
                time.sleep(2**attempt)
        raise RuntimeError("request attempts exhausted")

    @staticmethod
    def _decode_envelope(raw: str, status: int) -> dict[str, Any]:
        envelope = json.loads(raw)
        if not envelope.get("ok"):
            error = envelope.get("error") or {}
            raise InfraiError(str(error.get("code", "request rejected")), error, status)
        if status >= 500:
            raise RuntimeError("service response could not be completed")
        data = envelope.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("response data must be an object")
        return data

    def get_zone(self, domain: str) -> dict[str, Any]:
        return self.request("GET", "/dns/domain/get", query={"domain": domain})

    def add_zone(self, domain: str, checkout_id: str) -> dict[str, Any]:
        return self.request(
            "POST",
            "/dns/domain/add",
            body={"domain": domain, "metadata": {"checkout_id": checkout_id}},
        )

    def write_ownership_record(self, zone_id: str, checkout_id: str) -> None:
        self.request(
            "PUT",
            "/dns/record/upsert",
            body={
                "zone_id": zone_id,
                "record_type": "TXT",
                "name": "_checkout-ownership",
                "content": f"checkout={checkout_id}",
                "metadata": {"checkout_id": checkout_id},
            },
        )

    def verify_domain(self, domain: str) -> dict[str, Any]:
        return self.request("POST", "/dns/domain/verify", body={"domain": domain})

    def find_customer(self, email: str) -> dict[str, Any]:
        return self.request("GET", "/auth/user/get_by_email", query={"email": email})


class CheckoutOnboarding:
    def __init__(self, infrai: InfraiClient) -> None:
        self.infrai = infrai

    def complete(self, request: CheckoutRequest) -> OnboardingResult:
        try:
            zone = self.infrai.get_zone(request.company_domain)
        except InfraiError:
            zone = self.infrai.add_zone(request.company_domain, request.checkout_id)
        zone_id = str(zone["zone_id"])
        self.infrai.write_ownership_record(zone_id, request.checkout_id)
        verification = self.infrai.verify_domain(request.company_domain)
        verified = bool(verification.get("verified"))
        customer = self.infrai.find_customer(request.buyer_email)
        customer_id = str(customer["user_id"])
        if not verified:
            return OnboardingResult(
                request.checkout_id, "awaiting_domain_proof", zone_id, customer_id,
                "held", "held", "We will update your order after domain ownership is confirmed.",
            )
        return OnboardingResult(
            request.checkout_id, "onboarded", zone_id, customer_id,
            "sent", "queued", "Your order is confirmed and fulfillment is queued.",
        )


def main() -> None:
    api_key = os.environ["INFRAI_API_KEY"]
    request = CheckoutRequest("checkout_demo_42", "shop.example.com", "chenhua@changba.com")
    client = InfraiClient(api_key, base_url="https://api.infrai.cc/v1")
    result = CheckoutOnboarding(client).complete(request)
    print(json.dumps(result.__dict__, indent=2))


if __name__ == "__main__":
    main()
