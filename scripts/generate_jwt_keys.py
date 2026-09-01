"""生成 RS256 JWT 初始公私钥对（作为首次启动的迁移种子）。

用法:
    python scripts/generate_jwt_keys.py [--out-dir keys]

生成后:
    - 私钥 keys/jwt_private.pem 仅保留在签发服务（user-service），严禁对外分发/提交仓库
    - 公钥 keys/jwt_public.pem  可分发到任意需要校验 JWT 的兄弟服务

说明:
    - 该脚本生成的是"初始密钥"（无 kid 的旧命名）。服务首次启动时，
      KeyManager 会自动将其导入为当前签名密钥，并按 RFC 7638 分配唯一 kid，
      随后写入 keys/jwt_private_<kid>.pem 等文件并维护 jwt_state.json。
    - 后续密钥轮换由服务内置的后台任务自动完成，无需再手动运行本脚本。
"""

import argparse
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 RS256 JWT 初始公私钥对")
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

    print(f"[OK] 初始私钥已写入: {private_path.resolve()}（请保密，勿提交仓库）")
    print(f"[OK] 初始公钥已写入: {public_path.resolve()}（可分发到其他服务）")
    print(f"[OK] RSA 密钥长度: {args.bits} bits")
    print("[提示] 服务首次启动时会将这对密钥自动导入并分配 kid，后续轮换由内置后台任务完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
