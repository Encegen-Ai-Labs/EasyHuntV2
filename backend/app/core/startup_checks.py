"""Refuses to start in production with unsafe settings, and says so clearly in
development, so a placeholder secret cannot quietly reach a real deployment.
"""
from typing import List

from app.core.config import Settings
from app.core.logging import logger

PLACEHOLDER_JWT_SECRETS = {"", "dev-jwt-secret", "your_jwt_secret", "changeme"}
MIN_SECRET_LENGTH = 32


def find_problems(cfg: Settings) -> List[str]:
    """Settings that are unsafe outside a developer's machine."""
    problems: List[str] = []
    secret = cfg.jwt_signing_secret
    if secret in PLACEHOLDER_JWT_SECRETS or secret.startswith("your"):
        problems.append("The token-signing secret is a placeholder. Set APP_JWT_SECRET to a long random value.")
    elif len(secret) < MIN_SECRET_LENGTH:
        problems.append(f"The token-signing secret is shorter than {MIN_SECRET_LENGTH} characters.")
    if not cfg.APP_JWT_SECRET:
        problems.append("APP_JWT_SECRET is not set, so login tokens are signed with the Supabase JWT secret. Use a separate secret.")
    if cfg.SUPABASE_KEY == "dev-key" and not cfg.SUPABASE_SERVICE_ROLE_KEY:
        problems.append("No Supabase key is configured.")
    origins = cfg.cors_origin_list
    if "*" in origins:
        problems.append("CORS_ORIGINS allows every origin (*).")
    if any("localhost" in o or "127.0.0.1" in o for o in origins):
        problems.append("CORS_ORIGINS still lists localhost.")
    if cfg.ADMIN_PASSWORD:
        problems.append("ADMIN_PASSWORD is set in the environment. It is only read by scripts/create_admin.py; remove it after creating the admin.")
    if not cfg.RATE_LIMIT_ENABLED:
        problems.append("Rate limiting is switched off.")
    return problems


def run(cfg: Settings) -> None:
    """Production: raise on any problem. Anywhere else: log them as warnings."""
    problems = find_problems(cfg)
    if not problems:
        return
    if cfg.is_production:
        raise RuntimeError("Refusing to start in production:\n- " + "\n- ".join(problems))
    for problem in problems:
        logger.warning("startup.unsafe_setting | %s", problem)
