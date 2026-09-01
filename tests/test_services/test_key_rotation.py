"""JWT 密钥轮换与 JWKS 管理测试。"""

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt as jose_jwt

from app.core.key_manager import KeyManager
from app.core.security import create_access_token, decode_token


def _make_km(tmp_path, rotation_days=30, retire_days=1, **kwargs) -> KeyManager:
    return KeyManager(
        key_dir=tmp_path,
        rotation_interval_days=rotation_days,
        retire_days=retire_days,
        **kwargs,
    )


def _age_current_key(km: KeyManager, days: int) -> None:
    """把当前签名密钥的创建时间改到 N 天前，模拟密钥超龄。"""
    kid = km.current_kid
    km._key_times[kid]["created_at"] = (
        datetime.now(timezone.utc) - timedelta(days=days)
    ).isoformat()
    km._save_state()


class TestKidHeader:
    """JWT Header 应携带 kid 且可被本服务解码。"""

    def test_global_token_has_kid_and_roundtrip(self):
        token = create_access_token(subject="u", user_id=1, service_name="default")
        header = jose_jwt.get_unverified_header(token)
        assert header.get("alg") == "RS256"
        kid = header.get("kid")
        assert kid

        payload = decode_token(token)
        assert payload["user_id"] == 1
        assert payload["type"] == "access"


class TestBootstrap:
    """启动加载与旧 PEM 迁移。"""

    def test_generates_new_keypair_when_empty(self, tmp_path):
        km = _make_km(tmp_path)
        assert km.current_kid
        assert km.get_signing_key()[0] == km.current_kid
        assert (tmp_path / "jwt_state.json").is_file()
        # 每个 kid 都有对应的公私钥文件
        kid = km.current_kid
        assert (tmp_path / f"jwt_private_{kid}.pem").is_file()
        assert (tmp_path / f"jwt_public_{kid}.pem").is_file()
        # JWKS 至少一个 key，且带 kid
        jwks = km.get_jwks()
        assert len(jwks["keys"]) >= 1
        assert jwks["keys"][0]["kid"] == kid

    def test_imports_legacy_pem_and_assigns_kid(self, tmp_path):
        # 准备旧命名 PEM（模拟上一代部署留下的密钥）
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        legacy_dir = tmp_path / "legacy"
        legacy_dir.mkdir()
        legacy_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        priv_pem = legacy_private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_pem = legacy_private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        legacy_private_path = legacy_dir / "jwt_private.pem"
        legacy_public_path = legacy_dir / "jwt_public.pem"
        legacy_private_path.write_bytes(priv_pem)
        legacy_public_path.write_bytes(pub_pem)

        km = _make_km(
            tmp_path / "keys",
            legacy_private=str(legacy_private_path),
            legacy_public=str(legacy_public_path),
        )
        kid = km.current_kid
        assert (tmp_path / "keys" / f"jwt_private_{kid}.pem").is_file()
        assert (tmp_path / "keys" / f"jwt_public_{kid}.pem").is_file()
        # 旧 PEM 的公钥应等于导入后的当前公钥（迁移一致）
        old_pub = legacy_public_path.read_text(encoding="utf-8")
        assert km.get_public_key(kid).strip() == old_pub.strip()


class TestRotation:
    """密钥轮换：新密钥生效、旧公钥保留、旧 token 仍可验证。"""

    def test_rotation_switches_signing_key_and_keeps_old(self, tmp_path):
        km = _make_km(tmp_path)
        old_kid = km.current_kid

        # 用旧密钥签发一个"旧 token"
        old_priv = km.get_signing_key()[1]
        old_token = jose_jwt.encode(
            {"sub": "u", "user_id": 1, "type": "access"},
            old_priv,
            algorithm="RS256",
            headers={"kid": old_kid},
        )

        # 密钥超龄 -> 轮换
        _age_current_key(km, days=31)
        assert km.check_rotation() is True

        new_kid = km.current_kid
        assert new_kid != old_kid

        # JWKS 同时包含新旧两个 kid
        kids = [k["kid"] for k in km.get_jwks()["keys"]]
        assert old_kid in kids
        assert new_kid in kids

        # 旧 token 仍可用旧公钥验证（保留期内）
        old_pub = km.get_public_key(old_kid)
        assert old_pub is not None
        payload = jose_jwt.decode(old_token, old_pub, algorithms=["RS256"])
        assert payload["user_id"] == 1

    def test_rotation_not_triggered_before_interval(self, tmp_path):
        km = _make_km(tmp_path)
        kid = km.current_kid
        # 未超龄 -> 不轮换
        assert km.check_rotation() is False
        assert km.current_kid == kid

    def test_retired_key_removed_after_retire_period(self, tmp_path):
        km = _make_km(tmp_path, retire_days=1)
        old_kid = km.current_kid
        _age_current_key(km, days=31)
        assert km.check_rotation() is True

        # 轮换后旧 key 已被标记退役
        assert km._key_times[old_kid]["retired_at"] is not None

        # 超过保留期后清理：从 JWKS 与磁盘移除
        retired_at = datetime.fromisoformat(km._key_times[old_kid]["retired_at"])
        later = retired_at + timedelta(days=2)
        km.check_rotation(now=later)

        kids = [k["kid"] for k in km.get_jwks()["keys"]]
        assert old_kid not in kids
        assert km.get_public_key(old_kid) is None
        assert not (tmp_path / f"jwt_public_{old_kid}.pem").exists()
        assert not (tmp_path / f"jwt_private_{old_kid}.pem").exists()

    def test_jwks_stable_across_reload(self, tmp_path):
        km = _make_km(tmp_path)
        kid = km.current_kid
        # 重新加载同一目录，kid 稳定不变
        km2 = _make_km(tmp_path)
        assert km2.current_kid == kid
        assert km2.get_public_key(kid) == km.get_public_key(kid)

    def test_unknown_kid_public_key_returns_none(self, tmp_path):
        km = _make_km(tmp_path)
        assert km.get_public_key("no-such-kid") is None


@pytest.mark.asyncio
async def test_global_security_module_loaded(tmp_path):
    """全局 security 模块（真实 keys/ 目录）可正常签发并携带 kid。"""
    token = create_access_token(subject="s", user_id=7, service_name="forum")
    header = jose_jwt.get_unverified_header(token)
    assert header.get("kid")
    payload = decode_token(token)
    assert payload["user_id"] == 7
