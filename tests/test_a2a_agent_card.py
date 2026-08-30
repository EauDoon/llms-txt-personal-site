from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from a2a_agent_card import load_agent_card, publish_agent_card, validate_agent_card


class A2AAgentCardTests(unittest.TestCase):
    def card(self):
        return {
            "name": "Example Research Agent",
            "description": "Answers bounded research questions.",
            "supportedInterfaces": [
                {
                    "url": "https://agent.example.test/a2a/v1",
                    "protocolBinding": "HTTP+JSON",
                    "protocolVersion": "1.0",
                }
            ],
            "provider": {
                "organization": "Example Organization",
                "url": "https://example.test",
            },
            "version": "2.3.0",
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
            },
            "securitySchemes": {
                "bearer": {
                    "httpAuthSecurityScheme": {
                        "scheme": "Bearer",
                        "bearerFormat": "JWT",
                    }
                }
            },
            "securityRequirements": [],
            "defaultInputModes": ["text/plain", "application/json"],
            "defaultOutputModes": ["text/plain", "application/json"],
            "skills": [
                {
                    "id": "bounded-research",
                    "name": "Bounded research",
                    "description": "Researches a defined question and returns cited findings.",
                    "tags": ["research", "citations"],
                    "examples": ["Summarize the primary evidence for this claim."],
                }
            ],
        }

    def test_current_public_v1_card_validates(self) -> None:
        self.assertEqual(validate_agent_card(self.card()), [])

    def test_required_and_legacy_card_fields_fail_closed(self) -> None:
        card = self.card()
        del card["supportedInterfaces"]
        card.update(
            {
                "url": "https://agent.example.test/a2a",
                "protocolVersion": "0.3",
                "preferredTransport": "JSONRPC",
            }
        )

        issues = validate_agent_card(card)

        self.assertTrue(any("missing required" in issue for issue in issues))
        self.assertGreaterEqual(sum("legacy pre-v1" in issue for issue in issues), 3)

    def test_interfaces_require_v1_and_a_real_secure_service_endpoint(self) -> None:
        card = self.card()
        card["supportedInterfaces"] = [
            {
                "url": "https://agent.example.test/.well-known/agent-card.json",
                "protocolBinding": "HTTP+JSON",
                "protocolVersion": "0.3",
            },
            {
                "url": "https://[invalid",
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0.1",
            },
        ]

        issues = validate_agent_card(card)

        self.assertGreaterEqual(sum("major.minor version 1.x" in issue for issue in issues), 2)
        self.assertTrue(any("not the Agent Card" in issue for issue in issues))
        self.assertTrue(any("absolute HTTPS" in issue for issue in issues))

    def test_custom_binding_uses_a_uri_and_secure_endpoint(self) -> None:
        card = self.card()
        card["supportedInterfaces"] = [
            {
                "url": "wss://agent.example.test/a2a/socket",
                "protocolBinding": "https://example.test/bindings/websocket/v1",
                "protocolVersion": "1.0",
            }
        ]
        self.assertEqual(validate_agent_card(card), [])

        card["supportedInterfaces"][0]["protocolBinding"] = "WEBSOCKET"
        card["supportedInterfaces"][0]["url"] = "ws://agent.example.test/a2a/socket"
        issues = validate_agent_card(card)
        self.assertTrue(any("must be a URI" in issue for issue in issues))
        self.assertTrue(any("secure URL" in issue for issue in issues))

    def test_malformed_interface_values_report_issues_without_crashing(self) -> None:
        card = self.card()
        card["supportedInterfaces"] = [
            {
                "url": [],
                "protocolBinding": {"unexpected": True},
                "protocolVersion": ["1.0"],
                "tenant": {"unexpected": True},
            }
        ]

        issues = validate_agent_card(card)

        self.assertGreaterEqual(sum("must be a nonempty string" in issue for issue in issues), 4)

    def test_current_oauth_scheme_and_requirements_validate(self) -> None:
        card = self.card()
        card["securitySchemes"] = {
            "oauth": {
                "oauth2SecurityScheme": {
                    "oauth2MetadataUrl": "https://auth.example.test/.well-known/oauth-authorization-server",
                    "flows": {
                        "authorizationCode": {
                            "authorizationUrl": "https://auth.example.test/authorize",
                            "tokenUrl": "https://auth.example.test/token",
                            "scopes": {"research:read": "Read research results."},
                            "pkceRequired": True,
                        }
                    },
                }
            }
        }
        card["securityRequirements"] = [
            {"schemes": {"oauth": {"list": ["research:read"]}}}
        ]

        self.assertEqual(validate_agent_card(card), [])

    def test_invalid_security_details_and_references_fail_closed(self) -> None:
        card = self.card()
        card["securitySchemes"] = {
            "apiKey": {
                "apiKeySecurityScheme": {
                    "location": "body",
                    "name": "",
                }
            },
            "oauth": {
                "oauth2SecurityScheme": {
                    "flows": {
                        "authorizationCode": {
                            "authorizationUrl": "http://auth.example.test/authorize",
                            "scopes": [],
                        }
                    }
                }
            },
        }
        card["securityRequirements"] = [
            {
                "schemes": {
                    "missing": {"list": []},
                    "apiKey": [],
                }
            }
        ]

        issues = validate_agent_card(card)

        self.assertTrue(any("location must be query, header, or cookie" in issue for issue in issues))
        self.assertTrue(any("name must be a nonempty string" in issue for issue in issues))
        self.assertTrue(any("tokenUrl is required" in issue for issue in issues))
        self.assertTrue(any("authorizationUrl must be an absolute HTTPS URL" in issue for issue in issues))
        self.assertTrue(any("scopes must be an object" in issue for issue in issues))
        self.assertTrue(any("undefined security scheme" in issue for issue in issues))
        self.assertTrue(any("must contain only a list array" in issue for issue in issues))
        self.assertFalse(any("securitySchemes.apiKey is a credential-like field" in issue for issue in issues))

    def test_media_modes_follow_rfc_token_and_parameter_syntax(self) -> None:
        card = self.card()
        card["defaultInputModes"] = [
            'text/plain; charset="utf-8"',
            "application/vnd.example+json;version=1",
        ]
        self.assertEqual(validate_agent_card(card), [])

        for invalid in ("x()/y()", "text", "text/", "text/plain; charset", "text/plain, text/html"):
            invalid_card = self.card()
            invalid_card["defaultInputModes"] = [invalid]
            with self.subTest(invalid=invalid):
                self.assertTrue(
                    any("must be a media type" in issue for issue in validate_agent_card(invalid_card))
                )

    def test_credentials_and_duplicate_skill_ids_are_rejected(self) -> None:
        card = self.card()
        duplicate = copy.deepcopy(card["skills"][0])
        card["skills"].append(duplicate)
        card["capabilities"]["extensions"] = [
            {"uri": "https://example.test/extensions/private", "params": {"clientSecret": "do-not-publish"}}
        ]

        issues = validate_agent_card(card)

        self.assertTrue(any("duplicates another skill" in issue for issue in issues))
        self.assertTrue(any("credential-like field" in issue for issue in issues))

    def test_duplicate_json_keys_are_rejected_before_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "card.json"
            path.write_text('{"name":"first","name":"second"}', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                load_agent_card(path)

    def test_nonstandard_json_constants_are_rejected_before_publication(self) -> None:
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                output = root / "site"
                output.mkdir()
                source = root / "agent-card.local.json"
                payload = json.dumps(self.card())
                payload = payload[:-1] + ', "extensionValue": %s}' % constant
                source.write_text(payload, encoding="utf-8")

                with self.assertRaisesRegex(ValueError, "nonstandard JSON constant"):
                    publish_agent_card(
                        root,
                        output,
                        {"A2A_AGENT_CARD_PATH": "agent-card.local.json"},
                    )
                self.assertFalse((output / ".well-known" / "agent-card.json").exists())

    def test_credential_query_parameters_are_rejected_before_publication(self) -> None:
        for parameter in ("access_token", "clientSecret", "X-Amz-Signature", "api-key"):
            with self.subTest(parameter=parameter), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                output = root / "site"
                output.mkdir()
                card = self.card()
                card["supportedInterfaces"][0]["url"] += "?%s=do-not-publish" % parameter
                source = root / "agent-card.local.json"
                source.write_text(json.dumps(card), encoding="utf-8")

                with self.assertRaisesRegex(ValueError, "invalid A2A v1 Agent Card"):
                    publish_agent_card(
                        root,
                        output,
                        {"A2A_AGENT_CARD_PATH": "agent-card.local.json"},
                    )
                self.assertFalse((output / ".well-known" / "agent-card.json").exists())

    def test_publication_is_opt_in_and_preserves_validated_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "site"
            output.mkdir()
            self.assertFalse(publish_agent_card(root, output, {}))
            self.assertFalse((output / ".well-known" / "agent-card.json").exists())

            source = root / "agent-card.local.json"
            source.write_text(json.dumps(self.card(), indent=4) + "\n", encoding="utf-8")
            before = source.read_bytes()

            self.assertTrue(
                publish_agent_card(
                    root,
                    output,
                    {"A2A_AGENT_CARD_PATH": "agent-card.local.json"},
                )
            )
            published = output / ".well-known" / "agent-card.json"
            self.assertEqual(published.read_bytes(), before)

    def test_template_card_and_outside_source_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "site"
            destination = output / ".well-known" / "agent-card.json"
            destination.parent.mkdir(parents=True)
            destination.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "template must not publish"):
                publish_agent_card(root, output, {})

            destination.unlink()
            with self.assertRaisesRegex(ValueError, "project-relative"):
                publish_agent_card(
                    root,
                    output,
                    {"A2A_AGENT_CARD_PATH": "../outside.json"},
                )

    def test_host_configs_set_the_a2a_media_type(self) -> None:
        marker = "application/a2a+json; charset=utf-8"
        for name in ("_headers", "vercel.json", ".htaccess"):
            with self.subTest(name=name):
                self.assertIn(
                    marker,
                    (ROOT / "template" / name).read_text(encoding="utf-8"),
                )


if __name__ == "__main__":
    unittest.main()
