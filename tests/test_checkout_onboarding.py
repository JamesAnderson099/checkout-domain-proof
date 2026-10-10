import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from checkout_onboarding import CheckoutOnboarding, CheckoutRequest


class VerifiedDomainClient:
    def get_zone(self, domain):
        return {"zone_id": "zone_7"}

    def write_ownership_record(self, zone_id, checkout_id):
        self.record = (zone_id, checkout_id)

    def verify_domain(self, domain):
        return {"verified": False}

    def find_customer(self, email):
        return {"user_id": "user_19"}


def test_unverified_domain_holds_receipt_and_fulfillment():
    client = VerifiedDomainClient()
    result = CheckoutOnboarding(client).complete(
        CheckoutRequest("checkout_19", "store.example", "buyer@store.example")
    )

    assert client.record == ("zone_7", "checkout_19")
    assert result.status == "awaiting_domain_proof"
    assert result.receipt_status == "held"
    assert result.fulfillment_status == "held"
