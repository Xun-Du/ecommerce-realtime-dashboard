"""Create the M1 schema in the configured Supabase Postgres database."""

from sqlalchemy.exc import OperationalError

from backend.app.core.database import initialize_database


def main() -> None:
    try:
        initialize_database()
    except OperationalError as error:
        raise SystemExit(
            "无法连接 Supabase 数据库。请在 Supabase Dashboard 的 Connect 页面复制 "
            "Session Pooler 连接串，使用 postgresql+psycopg:// 前缀并保留 ?sslmode=require。"
        ) from error
    print("M1 数据库初始化完成：表、索引和默认实验配置已就绪。")


if __name__ == "__main__":
    main()
