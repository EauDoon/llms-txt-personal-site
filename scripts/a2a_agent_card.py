"""Fail-closed publication checks for an optional public A2A v1 Agent Card."""

from __future__ import annotations

import io
import json
import os
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit


CARD_PATH = Path(".well-known") / "agent-card.json"
REQUIRED_FIELDS = {
    "name",
    "description",
    "supportedInterfaces",
    "version",
    "capabilities",
    "defaultInputModes",
    "defaultOutputModes",
    "skills",
}
OPTIONAL_FIELDS = {
    "provider",
    "documentationUrl",
    "securitySchemes",
    "securityRequirements",
    "signatures",
    "iconUrl",
}
LEGACY_FIELDS = {
    "url",
    "protocolVersion",
    "preferredTransport",
    "additionalInterfaces",
    "supportsAuthenticatedExtendedCard",
}
SECRET_FIELD_NAMES = {
    "token",
    "accesstoken",
    "refreshtoken",
    "clientsecret",
    "secret",
    "password",
    "privatekey",
    "apikey",
    "credential",
    "credentials",
}
SECURITY_SCHEME_TYPES = {
    "apiKeySecurityScheme",
    "httpAuthSecurityScheme",
    "oauth2SecurityScheme",
    "openIdConnectSecurityScheme",
    "mtlsSecurityScheme",
}
HTTP_TOKEN = r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+"
QUOTED_VALUE = r'"(?:[\t !#-\[\]-~]|\\[\t -~])*"'
MIME_TYPE = re.compile(
    r"^%s/%s(?:[ \t]*;[ \t]*%s[ \t]*=[ \t]*(?:%s|%s))*$"
    % (HTTP_TOKEN, HTTP_TOKEN, HTTP_TOKEN, HTTP_TOKEN, QUOTED_VALUE)
)
PROTOCOL_VERSION = re.compile(r"^1\.\d+$")
BASE64URL = re.compile(r"^[A-Za-z0-9_-]+$")
GRPC_ADDRESS = re.compile(r"^(?:[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?|\[[0-9A-Fa-f:]+\]):([0-9]{1,5})$")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: %s" % key)
        result[key] = value
    return result


def load_agent_card(path):
    with io.open(path, encoding="utf-8") as source:
        card = parse_agent_card(source.read())
    return card


def parse_agent_card(text):
    def reject_constant(value):
        raise ValueError("nonstandard JSON constant is not allowed: %s" % value)

    card = json.loads(
        text,
        object_pairs_hook=_unique_object,
        parse_constant=reject_constant,
    )
    if not isinstance(card, dict):
        raise ValueError("Agent Card must be a JSON object")
    return card


def _nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def _credential_query_names(parsed):
    names = []
    components = {
        "token",
        "secret",
        "key",
        "password",
        "passwd",
        "authorization",
        "auth",
        "credential",
        "credentials",
        "signature",
        "jwt",
    }
    normalized_names = SECRET_FIELD_NAMES | {
        "authorization",
        "auth",
        "key",
        "passwd",
        "secret",
        "signature",
        "jwt",
    }
    for name, _ in parse_qsl(parsed.query, keep_blank_values=True):
        words = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
        parts = {part for part in re.split(r"[^a-z0-9]+", words.lower()) if part}
        normalized = re.sub(r"[^a-z0-9]", "", name.lower())
        if normalized in normalized_names or parts & components:
            names.append(name)
    return names


def _https_url(value):
    if not _nonempty_string(value):
        return False
    try:
        parsed = urlsplit(value)
        parsed.port
        hostname = parsed.hostname
    except ValueError:
        return False
    return (
        parsed.scheme.lower() == "https"
        and bool(hostname)
        and not any(character.isspace() for character in value)
        and not parsed.username
        and not parsed.password
        and not parsed.fragment
        and not _credential_query_names(parsed)
    )


def _secure_custom_url(value):
    if not _nonempty_string(value):
        return False
    try:
        parsed = urlsplit(value)
        parsed.port
        hostname = parsed.hostname
    except ValueError:
        return False
    return (
        parsed.scheme.lower() in {"https", "wss", "grpcs"}
        and bool(hostname)
        and not any(character.isspace() for character in value)
        and not parsed.username
        and not parsed.password
        and not parsed.fragment
        and not _credential_query_names(parsed)
    )


def _grpc_endpoint(value):
    if _https_url(value):
        return True
    match = GRPC_ADDRESS.fullmatch(value) if isinstance(value, str) else None
    if not match:
        return False
    return 0 < int(match.group(1)) <= 65535


def _string_list(value, path, issues, media_types=False, allow_empty=False):
    if not isinstance(value, list) or (not value and not allow_empty):
        issues.append("%s must be a nonempty array" % path)
        return
    for index, item in enumerate(value):
        item_path = "%s[%d]" % (path, index)
        if not _nonempty_string(item):
            issues.append("%s must be a nonempty string" % item_path)
        elif media_types and not MIME_TYPE.fullmatch(item):
            issues.append("%s must be a media type such as text/plain" % item_path)


def _optional_strings(value, fields, path, issues):
    for field in sorted(fields):
        if field in value and not isinstance(value[field], str):
            issues.append("%s.%s must be a string" % (path, field))


def _unknown_fields(value, allowed, path, issues):
    unknown = sorted(set(value) - set(allowed))
    if unknown:
        issues.append("%s has unsupported fields: %s" % (path, ", ".join(unknown)))


def _stable_identity(*values):
    return tuple(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        for value in values
    )


def _check_public_fields(value, path, issues):
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            password_flow = normalized == "password" and path.endswith(".flows")
            public_map_key = path.endswith((".securitySchemes", ".schemes", ".scopes"))
            if normalized in SECRET_FIELD_NAMES and not password_flow and not public_map_key:
                issues.append("%s.%s is a credential-like field and must not be public" % (path, key))
            _check_public_fields(item, "%s.%s" % (path, key), issues)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_public_fields(item, "%s[%d]" % (path, index), issues)


def _validate_interfaces(value, issues):
    if not isinstance(value, list) or not value:
        issues.append("supportedInterfaces must be a nonempty array")
        return
    seen = set()
    for index, interface in enumerate(value):
        path = "supportedInterfaces[%d]" % index
        if not isinstance(interface, dict):
            issues.append("%s must be an object" % path)
            continue
        _unknown_fields(interface, {"url", "protocolBinding", "protocolVersion", "tenant"}, path, issues)
        for field in ("url", "protocolBinding", "protocolVersion"):
            if not _nonempty_string(interface.get(field)):
                issues.append("%s.%s must be a nonempty string" % (path, field))
        url = interface.get("url")
        binding = interface.get("protocolBinding")
        version = interface.get("protocolVersion")
        tenant = interface.get("tenant")
        if "tenant" in interface and not _nonempty_string(tenant):
            issues.append("%s.tenant must be a nonempty string when present" % path)
        if _nonempty_string(version) and not PROTOCOL_VERSION.fullmatch(version):
            issues.append("%s.protocolVersion must use A2A major.minor version 1.x" % path)
        try:
            endpoint_path = urlsplit(url).path if _nonempty_string(url) else ""
        except ValueError:
            endpoint_path = ""
        if endpoint_path.rstrip("/").endswith("/.well-known/agent-card.json"):
            issues.append("%s.url must point to an A2A service, not the Agent Card" % path)
        if _nonempty_string(binding) and binding in {"JSONRPC", "HTTP+JSON"}:
            if not _https_url(url):
                issues.append("%s.url must be an absolute HTTPS URL" % path)
        elif _nonempty_string(binding) and binding == "GRPC":
            if not _grpc_endpoint(url):
                issues.append("%s.url must be an HTTPS URL or a valid gRPC host:port" % path)
        elif _nonempty_string(binding):
            try:
                custom_binding = urlsplit(binding)
            except ValueError:
                custom_binding = None
            if custom_binding is None or not custom_binding.scheme:
                issues.append("%s.protocolBinding must be a URI for a custom binding" % path)
            if not _secure_custom_url(url):
                issues.append("%s.url must use a secure URL for a custom binding" % path)
        identity = _stable_identity(url, binding, version, tenant)
        if identity in seen:
            issues.append("%s duplicates an earlier interface" % path)
        seen.add(identity)


def _validate_capabilities(value, issues):
    if not isinstance(value, dict):
        issues.append("capabilities must be an object")
        return
    allowed = {"streaming", "pushNotifications", "extensions", "extendedAgentCard"}
    _unknown_fields(value, allowed, "capabilities", issues)
    for key in ("streaming", "pushNotifications", "extendedAgentCard"):
        if key in value and not isinstance(value[key], bool):
            issues.append("capabilities.%s must be a boolean" % key)
    if "extensions" in value:
        extensions = value["extensions"]
        if not isinstance(extensions, list):
            issues.append("capabilities.extensions must be an array")
        else:
            for index, extension in enumerate(extensions):
                path = "capabilities.extensions[%d]" % index
                if not isinstance(extension, dict):
                    issues.append("%s must be an object" % path)
                    continue
                _unknown_fields(extension, {"uri", "description", "required", "params"}, path, issues)
                if "uri" in extension:
                    uri = extension["uri"]
                    try:
                        has_scheme = _nonempty_string(uri) and bool(urlsplit(uri).scheme)
                    except ValueError:
                        has_scheme = False
                    if not has_scheme:
                        issues.append("%s.uri must be an absolute URI" % path)
                _optional_strings(extension, {"description"}, path, issues)
                if "required" in extension and not isinstance(extension["required"], bool):
                    issues.append("%s.required must be a boolean" % path)
                if "params" in extension and not isinstance(extension["params"], dict):
                    issues.append("%s.params must be an object" % path)


def _validate_skills(value, security_scheme_names, issues):
    if not isinstance(value, list) or not value:
        issues.append("skills must be a nonempty array")
        return
    seen_ids = set()
    allowed = {
        "id",
        "name",
        "description",
        "tags",
        "examples",
        "inputModes",
        "outputModes",
        "securityRequirements",
    }
    for index, skill in enumerate(value):
        path = "skills[%d]" % index
        if not isinstance(skill, dict):
            issues.append("%s must be an object" % path)
            continue
        _unknown_fields(skill, allowed, path, issues)
        for field in ("id", "name", "description"):
            if not _nonempty_string(skill.get(field)):
                issues.append("%s.%s must be a nonempty string" % (path, field))
        skill_id = skill.get("id")
        if _nonempty_string(skill_id):
            if skill_id in seen_ids:
                issues.append("%s.id duplicates another skill" % path)
            seen_ids.add(skill_id)
        _string_list(skill.get("tags"), path + ".tags", issues)
        for field in ("inputModes", "outputModes"):
            if field in skill:
                _string_list(skill[field], path + "." + field, issues, media_types=True)
        if "examples" in skill:
            _string_list(skill["examples"], path + ".examples", issues, allow_empty=True)
        if "securityRequirements" in skill:
            _validate_security_requirements(
                skill["securityRequirements"],
                security_scheme_names,
                path + ".securityRequirements",
                issues,
            )


def _validate_provider(value, issues):
    if not isinstance(value, dict):
        issues.append("provider must be an object")
        return
    _unknown_fields(value, {"organization", "url"}, "provider", issues)
    if not _nonempty_string(value.get("organization")):
        issues.append("provider.organization must be a nonempty string")
    if not _https_url(value.get("url")):
        issues.append("provider.url must be an absolute HTTPS URL")


def _validate_scopes(value, path, issues):
    if not isinstance(value, dict):
        issues.append("%s must be an object" % path)
        return
    for name, description in value.items():
        if not _nonempty_string(name):
            issues.append("%s scope names must be nonempty strings" % path)
        if not isinstance(description, str):
            issues.append("%s.%s must be a string" % (path, name))


def _validate_oauth_flow(value, flow_name, path, issues):
    specifications = {
        "authorizationCode": (
            {"authorizationUrl", "tokenUrl", "refreshUrl", "scopes", "pkceRequired"},
            {"authorizationUrl", "tokenUrl", "scopes"},
        ),
        "clientCredentials": (
            {"tokenUrl", "refreshUrl", "scopes"},
            {"tokenUrl", "scopes"},
        ),
        "deviceCode": (
            {"deviceAuthorizationUrl", "tokenUrl", "refreshUrl", "scopes"},
            {"deviceAuthorizationUrl", "tokenUrl", "scopes"},
        ),
        "implicit": (
            {"authorizationUrl", "refreshUrl", "scopes"},
            {"authorizationUrl", "scopes"},
        ),
        "password": (
            {"tokenUrl", "refreshUrl", "scopes"},
            {"tokenUrl", "scopes"},
        ),
    }
    if not isinstance(value, dict):
        issues.append("%s must be an object" % path)
        return
    allowed, required = specifications[flow_name]
    _unknown_fields(value, allowed, path, issues)
    for field in sorted(required - set(value)):
        issues.append("%s.%s is required" % (path, field))
    for field in ("authorizationUrl", "deviceAuthorizationUrl", "tokenUrl", "refreshUrl"):
        if field in value and not _https_url(value[field]):
            issues.append("%s.%s must be an absolute HTTPS URL" % (path, field))
    if "scopes" in value:
        _validate_scopes(value["scopes"], path + ".scopes", issues)
    if "pkceRequired" in value and not isinstance(value["pkceRequired"], bool):
        issues.append("%s.pkceRequired must be a boolean" % path)


def _validate_security_scheme_details(scheme_type, value, path, issues):
    if not isinstance(value, dict):
        issues.append("%s scheme details must be an object" % path)
        return
    if scheme_type == "apiKeySecurityScheme":
        _unknown_fields(value, {"description", "location", "name"}, path, issues)
        _optional_strings(value, {"description"}, path, issues)
        if value.get("location") not in {"query", "header", "cookie"}:
            issues.append("%s.location must be query, header, or cookie" % path)
        if not _nonempty_string(value.get("name")):
            issues.append("%s.name must be a nonempty string" % path)
    elif scheme_type == "httpAuthSecurityScheme":
        _unknown_fields(value, {"description", "scheme", "bearerFormat"}, path, issues)
        _optional_strings(value, {"description", "bearerFormat"}, path, issues)
        if not _nonempty_string(value.get("scheme")):
            issues.append("%s.scheme must be a nonempty string" % path)
    elif scheme_type == "oauth2SecurityScheme":
        _unknown_fields(value, {"description", "flows", "oauth2MetadataUrl"}, path, issues)
        _optional_strings(value, {"description"}, path, issues)
        if "oauth2MetadataUrl" in value and not _https_url(value["oauth2MetadataUrl"]):
            issues.append("%s.oauth2MetadataUrl must be an absolute HTTPS URL" % path)
        flows = value.get("flows")
        flow_names = {"authorizationCode", "clientCredentials", "deviceCode", "implicit", "password"}
        if not isinstance(flows, dict) or len(flows) != 1 or not set(flows).issubset(flow_names):
            issues.append("%s.flows must contain exactly one A2A OAuth flow" % path)
        else:
            flow_name = next(iter(flows))
            _validate_oauth_flow(
                flows[flow_name], flow_name, path + ".flows." + flow_name, issues
            )
    elif scheme_type == "openIdConnectSecurityScheme":
        _unknown_fields(value, {"description", "openIdConnectUrl"}, path, issues)
        _optional_strings(value, {"description"}, path, issues)
        if not _https_url(value.get("openIdConnectUrl")):
            issues.append("%s.openIdConnectUrl must be an absolute HTTPS URL" % path)
    elif scheme_type == "mtlsSecurityScheme":
        _unknown_fields(value, {"description"}, path, issues)
        _optional_strings(value, {"description"}, path, issues)


def _validate_security_schemes(value, issues):
    if not isinstance(value, dict) or not value:
        issues.append("securitySchemes must be a nonempty object when present")
        return
    for name, scheme in value.items():
        path = "securitySchemes.%s" % name
        if not _nonempty_string(name) or not isinstance(scheme, dict):
            issues.append("%s must be a named object" % path)
            continue
        variants = set(scheme) & SECURITY_SCHEME_TYPES
        if len(variants) != 1 or set(scheme) != variants:
            issues.append("%s must contain exactly one A2A security scheme type" % path)
        else:
            scheme_type = next(iter(variants))
            _validate_security_scheme_details(
                scheme_type, scheme[scheme_type], path + "." + scheme_type, issues
            )


def _validate_security_requirements(value, scheme_names, path, issues):
    if not isinstance(value, list):
        issues.append("%s must be an array" % path)
        return
    for index, requirement in enumerate(value):
        requirement_path = "%s[%d]" % (path, index)
        if not isinstance(requirement, dict) or set(requirement) != {"schemes"}:
            issues.append("%s must contain only a schemes object" % requirement_path)
            continue
        schemes = requirement["schemes"]
        if not isinstance(schemes, dict) or not schemes:
            issues.append("%s.schemes must be a nonempty object" % requirement_path)
            continue
        for name, scopes in schemes.items():
            scheme_path = "%s.schemes.%s" % (requirement_path, name)
            if not _nonempty_string(name):
                issues.append("%s scheme names must be nonempty strings" % requirement_path)
            elif name not in scheme_names:
                issues.append("%s references an undefined security scheme" % scheme_path)
            if not isinstance(scopes, dict) or set(scopes) != {"list"}:
                issues.append("%s must contain only a list array" % scheme_path)
                continue
            _string_list(scopes["list"], scheme_path + ".list", issues, allow_empty=True)


def _validate_signatures(value, issues):
    if not isinstance(value, list) or not value:
        issues.append("signatures must be a nonempty array when present")
        return
    for index, signature in enumerate(value):
        path = "signatures[%d]" % index
        if not isinstance(signature, dict):
            issues.append("%s must be an object" % path)
            continue
        unknown = sorted(set(signature) - {"protected", "signature", "header"})
        if unknown:
            issues.append("%s has unsupported fields: %s" % (path, ", ".join(unknown)))
        for field in ("protected", "signature"):
            if (
                not _nonempty_string(signature.get(field))
                or not BASE64URL.fullmatch(signature[field])
            ):
                issues.append("%s.%s must be a nonempty base64url string" % (path, field))
        if "header" in signature and not isinstance(signature["header"], dict):
            issues.append("%s.header must be an object" % path)


def validate_agent_card(card):
    """Return structural and public-surface violations for an A2A v1 card."""
    if not isinstance(card, dict):
        return ["Agent Card must be a JSON object"]
    issues = []
    for field in sorted(REQUIRED_FIELDS):
        if field not in card:
            issues.append("missing required Agent Card field: %s" % field)
    for field in sorted(set(card) & LEGACY_FIELDS):
        issues.append("legacy pre-v1 Agent Card field is not allowed: %s" % field)
    unknown = sorted(set(card) - REQUIRED_FIELDS - OPTIONAL_FIELDS - LEGACY_FIELDS)
    if unknown:
        issues.append("unsupported Agent Card fields: %s" % ", ".join(unknown))
    for field in ("name", "description", "version"):
        if field in card and not _nonempty_string(card[field]):
            issues.append("%s must be a nonempty string" % field)
    if "supportedInterfaces" in card:
        _validate_interfaces(card["supportedInterfaces"], issues)
    if "capabilities" in card:
        _validate_capabilities(card["capabilities"], issues)
    for field in ("defaultInputModes", "defaultOutputModes"):
        if field in card:
            _string_list(card[field], field, issues, media_types=True)
    security_scheme_names = (
        set(card.get("securitySchemes", {}))
        if isinstance(card.get("securitySchemes"), dict)
        else set()
    )
    if "skills" in card:
        _validate_skills(card["skills"], security_scheme_names, issues)
    if "provider" in card:
        _validate_provider(card["provider"], issues)
    for field in ("documentationUrl", "iconUrl"):
        if field in card and not _https_url(card[field]):
            issues.append("%s must be an absolute HTTPS URL" % field)
    if "securitySchemes" in card:
        _validate_security_schemes(card["securitySchemes"], issues)
    if "securityRequirements" in card:
        _validate_security_requirements(
            card["securityRequirements"],
            security_scheme_names,
            "securityRequirements",
            issues,
        )
    if "signatures" in card:
        _validate_signatures(card["signatures"], issues)
    _check_public_fields(card, "card", issues)
    return issues


def publish_agent_card(repo_root, output_dir, cfg):
    """Validate and copy an explicitly configured card into the well-known path."""
    destination = Path(output_dir) / CARD_PATH
    configured = cfg.get("A2A_AGENT_CARD_PATH")
    if os.path.lexists(destination):
        raise ValueError(
            "template must not publish an Agent Card; use A2A_AGENT_CARD_PATH for explicit validation"
        )
    if configured is None:
        return False
    if not _nonempty_string(configured):
        raise ValueError("A2A_AGENT_CARD_PATH must be a nonempty relative JSON path")
    relative = Path(configured)
    drive_like = bool(relative.parts and re.match(r"^[A-Za-z]:", relative.parts[0]))
    if (
        relative.is_absolute()
        or relative.drive
        or drive_like
        or ".." in relative.parts
        or relative.suffix.lower() != ".json"
        or (relative.parts and relative.parts[0].casefold() == "site")
    ):
        raise ValueError("A2A_AGENT_CARD_PATH must be a project-relative .json file")
    root = Path(repo_root).resolve()
    try:
        source = (root / relative).resolve(strict=True)
        source.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ValueError("A2A_AGENT_CARD_PATH must resolve to a file inside the project") from exc
    if not source.is_file():
        raise ValueError("A2A_AGENT_CARD_PATH must resolve to a regular file")
    try:
        source_bytes = source.read_bytes()
        source_text = source_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError("A2A_AGENT_CARD_PATH must be readable UTF-8 JSON") from exc
    card = parse_agent_card(source_text)
    issues = validate_agent_card(card)
    if issues:
        raise ValueError("invalid A2A v1 Agent Card:\n  - " + "\n  - ".join(issues))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source_bytes)
    print("  published validated A2A v1 Agent Card at /.well-known/agent-card.json")
    return True
