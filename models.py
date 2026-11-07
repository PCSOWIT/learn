from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class User(Base):
    """用户表模型，映射数据库中的 users 表"""

    # 指定对应的数据库表名
    __tablename__ = "users"

    # 主键，使用字符串类型（通常是 UUID），唯一标识每条记录
    id: Mapped[str] = mapped_column(primary_key=True)

    # 用户名，设置唯一约束，不允许重复
    username: Mapped[str] = mapped_column(unique=True)

    # 密码哈希值，存储加密后的密码（不存明文）
    password_hash: Mapped[str]