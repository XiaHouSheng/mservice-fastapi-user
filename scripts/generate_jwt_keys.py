"""生成 RS256 JWT 公私钥对。

用法:
    python scripts/generate_jwt_keys.py [--out-dir keys]

生成后:
    - 私钥 keys/jwt_private.pem 仅保留在签发服务（user-service），严禁对外分发/提交仓库
    - 公钥 keys/jwt_public.pem  可分发到任意需要校验 JWT 的兄弟服务
"""

import argparse
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 RS256 JWT 公私钥对")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("keys"),
        help="密钥输出目录（默认 ./keys）",
    )
    parser.add_argument(
        "--bits",
        type=int,
        default=2048,
        help="RSA 密钥长度（默认 2048）",
    )
    args = parser.parse_args()

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=args.bits)

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_path = out_dir / "jwt_private.pem"
    public_path = out_dir / "jwt_public.pem"
    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)

    print(f"[OK] 私钥已写入: {private_path.resolve()}（请保密，勿提交仓库）")
    print(f"[OK] 公钥已写入: {public_path.resolve()}（可分发到其他服务）")
    print(f"[OK] RSA 密钥长度: {args.bits} bits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
