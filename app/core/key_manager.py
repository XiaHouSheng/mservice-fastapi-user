"""JWT 密钥管理与自动轮换（RS256 非对称）。

设计要点：
- 每套 RSA 公私钥对应唯一 ``kid``（RFC 7638 JWK thumbprint，稳定且唯一）。
- 密钥以 PEM 文件保存在密钥目录：``jwt_private_<kid>.pem`` / ``jwt_public_<kid>.pem``。
- 状态记录在 ``jwt_state.json``：当前签名 kid、每个 kid 的创建 / 退役时间。
- 启动时加载当前密钥；后台定时检查：超龄则生成新密钥并设为当前签名密钥，
  旧公钥在保留期（>= 最长 JWT 有效期）过后自动删除。
- JWKS 同时暴露当前与未过期的旧公钥，支持其他服务按 kid 验证与后续密钥轮换。
- 仅使用本地文件，不引入数据库或额外基础设施。
"""

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose.jwk import RSAKey

STATE_FILE = "jwt_state.json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def kid_from_public_pem(public_pem: str) -> str:
    """按 RFC 7638 计算公钥 JWK 的 SHA-256 thumbprint 作为 kid。"""
    rsa_key = RSAKey(public_pem.encode("utf-8"), algorithm="RS256")
    jwk = rsa_key.to_dict()
    canonical = json.dumps(
        {"e": jwk["e"], "kty": "RSA", "n": jwk["n"]},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _b64url(hashlib.sha256(canonical).digest())


def _generate_keypair(key_size: int = 2048) -> tuple[str, str]:
    """生成新的 RSA 私钥 / 公钥 PEM。"""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    return private_pem, public_pem


def _pem_key_matches(private_pem: str, public_pem: str) -> bool:
    """校验私钥与公钥是否属于同一密钥对。"""
    try:
        priv_obj = serialization.load_pem_private_key(private_pem.encode("utf-8"), password=None)
        pub_obj = serialization.load_pem_public_key(public_pem.encode("utf-8"))
        derived = priv_obj.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        actual = pub_obj.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return derived == actual
    except Exception:
        return False


class KeyManager:
    """管理 JWT 密钥生命周期：加载、签发密钥获取、按 kid 校验、轮换与清理。"""

    def __init__(
        self,
        key_dir: str | Path,
        rotation_interval_days: int = 30,
        retire_days: int = 8,
        legacy_private: str | None = None,
        legacy_public: str | None = None,
    ) -> None:
        self.key_dir = Path(key_dir)
        self.key_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self.key_dir / STATE_FILE
        self.rotation_interval = timedelta(days=rotation_interval_days)
        self.retire_delta = timedelta(days=retire_days)
        self._legacy_private = legacy_private
        self._legacy_public = legacy_public

        self._priv_keys: dict[str, str] = {}
        self._pub_keys: dict[str, str] = {}
        self._key_times: dict[str, dict[str, Any]] = {}
        self._current_kid: str | None = None

        self.load()

    # ---------- 加载 / 初始化 ----------

    def load(self) -> None:
        """从磁盘加载密钥状态；无可用密钥时自动初始化。"""
        state = self._read_state()
        if state:
            self._current_kid = state.get("current_kid")
            self._key_times = state.get("keys") or {}
            for kid in list(self._key_times):
                pub = self._read_pem(kid, private=False)
                if pub is not None:
                    self._pub_keys[kid] = pub
                priv = self._read_pem(kid, private=True)
                if priv is not None:
                    self._priv_keys[kid] = priv

        if not self._pub_keys:
            self._bootstrap()
        elif self._current_kid not in self._pub_keys:
            # 当前签名密钥文件缺失：生成新密钥并接管
            self._rotate(initial=True)
        self._save_state()

    def _bootstrap(self) -> None:
        """无密钥时：优先导入旧 PEM（迁移），否则生成新密钥对。"""
        priv = self._resolve_legacy(self._legacy_private)
        pub = self._resolve_legacy(self._legacy_public)
        if priv and pub and _pem_key_matches(priv, pub):
            kid = kid_from_public_pem(pub)
            self._import_keypair(kid, priv, pub)
            self._current_kid = kid
            return
        self._rotate(initial=True)

    def _resolve_legacy(self, value: str | None) -> str | None:
        """旧 PEM 值可能为 PEM 字符串或文件路径。"""
        if not value:
            return None
        if "-----BEGIN" in value:
            return value
        path = Path(value)
        if path.is_file():
            return path.read_text(encoding="utf-8")
        return None

    # ---------- 对外接口 ----------

    @property
    def current_kid(self) -> str:
        assert self._current_kid is not None
        return self._current_kid

    def get_signing_key(self) -> tuple[str, str]:
        """返回 (当前 kid, 当前私钥 PEM)，用于签发。"""
        return self.current_kid, self._priv_keys[self.current_kid]

    def get_public_key(self, kid: str) -> str | None:
        """按 kid 返回公钥 PEM；未知 kid 返回 None。"""
        return self._pub_keys.get(kid)

    def get_active_kids(self) -> list[str]:
        """当前活跃（可验证）的公钥 kid 列表。"""
        return sorted(self._pub_keys.keys())

    def get_jwks(self, algorithm: str = "RS256") -> dict[str, Any]:
        """返回 JWKS：包含当前与未过期的旧公钥（多 kid）。"""
        keys = []
        for kid, pub_pem in sorted(self._pub_keys.items()):
            jwk = RSAKey(pub_pem.encode("utf-8"), algorithm=algorithm).to_dict()
            jwk["kid"] = kid
            jwk["use"] = "sig"
            keys.append(jwk)
        return {"keys": keys}

    # ---------- 轮换与清理 ----------

    def check_rotation(self, now: datetime | None = None) -> bool:
        """定期检查：清理超期旧公钥，必要时轮换生成新密钥。返回是否轮换。"""
        now = now or _now()
        self._cleanup_retired(now)

        if self._current_kid is None:
            self._rotate(initial=True)
            return True

        created = datetime.fromisoformat(self._key_times[self._current_kid]["created_at"])
        if created + self.rotation_interval <= now:
            self._rotate()
            return True
        return False

    def rotate_now(self) -> str:
        """手动强制轮换，返回新 kid（测试 / 运维用）。"""
        self._rotate()
        return self.current_kid

    def _rotate(self, initial: bool = False) -> None:
        """生成新密钥对并设为当前签名密钥，旧密钥标记为已退役。"""
        private_pem, public_pem = _generate_keypair()
        kid = kid_from_public_pem(public_pem)
        if not initial and self._current_kid and self._current_kid in self._key_times:
            self._key_times[self._current_kid]["retired_at"] = _now().isoformat()
        self._import_keypair(kid, private_pem, public_pem)
        self._current_kid = kid
        self._save_state()

    def _cleanup_retired(self, now: datetime) -> None:
        """删除超过保留期的旧公钥（及对应私钥 / 状态）。"""
        for kid in list(self._key_times):
            retired = self._key_times[kid].get("retired_at")
            if not retired:
                continue
            retired_dt = datetime.fromisoformat(retired)
            if retired_dt + self.retire_delta <= now:
                self._remove_key(kid)

    def _remove_key(self, kid: str) -> None:
        self._priv_keys.pop(kid, None)
        self._pub_keys.pop(kid, None)
        self._key_times.pop(kid, None)
        for private in (True, False):
            path = self.key_dir / self._pem_name(kid, private)
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        self._save_state()

    # ---------- 内部工具 ----------

    def _import_keypair(self, kid: str, private_pem: str, public_pem: str) -> None:
        self._priv_keys[kid] = private_pem
        self._pub_keys[kid] = public_pem
        self._key_times[kid] = {"created_at": _now().isoformat(), "retired_at": None}
        self._write_pem(kid, private_pem, private=True)
        self._write_pem(kid, public_pem, private=False)

    @staticmethod
    def _pem_name(kid: str, private: bool) -> str:
        return f"jwt_{'private' if private else 'public'}_{kid}.pem"

    def _read_pem(self, kid: str, private: bool) -> str | None:
        path = self.key_dir / self._pem_name(kid, private)
        if path.is_file():
            return path.read_text(encoding="utf-8")
        return None

    def _write_pem(self, kid: str, pem: str, private: bool) -> None:
        path = self.key_dir / self._pem_name(kid, private)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(pem, encoding="utf-8")
        tmp.replace(path)

    def _read_state(self) -> dict[str, Any] | None:
        if not self._state_file.is_file():
            return None
        try:
            return json.loads(self._state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _save_state(self) -> None:
        data = {
            "current_kid": self._current_kid,
            "rotation_interval_days": self.rotation_interval.days,
            "retire_days": self.retire_delta.days,
            "keys": self._key_times,
        }
        tmp = self._state_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._state_file)


__all__ = ["KeyManager", "kid_from_public_pem"]
