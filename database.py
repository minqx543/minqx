from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import os

# رابط قاعدة البيانات من متغير البيئة
DATABASE_URL = os.environ.get("DATABASE_URL")

# إعدادات الاتصال بقاعدة البيانات
engine = create_engine(DATABASE_URL, connect_args={}, echo=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# تعريف كلاس User
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String)
    points = Column(Integer, default=0)
    referrals_count = Column(Integer, default=0)  # عدد الإحالات للمستخدم
    created_at = Column(DateTime, default=datetime.utcnow)  # تاريخ الانضمام

    # الدالة لزيادة النقاط
    def increase_points(self, points):
        self.points += points

    # الدالة لزيادة الإحالات
    def increase_referrals(self):
        self.referrals_count += 1

# تعريف كلاس Referral
class Referral(Base):
    __tablename__ = 'referrals'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    referred_by = Column(Integer, ForeignKey('users.id'))
    date = Column(DateTime, default=datetime.utcnow)  # تاريخ الإحالة

    user = relationship("User", foreign_keys=[user_id])
    referrer = relationship("User", foreign_keys=[referred_by])

    # إضافة نقاط للمستخدم المحيل عندما تتم الإحالة
    reward_points = Column(Integer, default=100)  # 100 نقطة للمستخدم المحيل

    # الدالة لزيادة نقاط المستخدم المحيل
    def reward_referrer(self, session):
        referrer_user = session.query(User).filter(User.id == self.referred_by).first()
        if referrer_user:
            referrer_user.increase_points(self.reward_points)
            session.commit()

# إنشاء الجداول في قاعدة البيانات
def init_db():
    Base.metadata.create_all(bind=engine)

# للحصول على الجلسة (Session) من قاعدة البيانات
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# إضافة مستخدم جديد
def add_user(db, telegram_id, username):
    db_user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not db_user:
        db_user = User(telegram_id=telegram_id, username=username)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    return db_user

# إضافة إحالة جديدة
def add_referral(db, user_id, referred_by):
    db_referral = Referral(user_id=user_id, referred_by=referred_by)
    db.add(db_referral)
    db.commit()

    # مكافأة المحيل بالنقاط
    db_referral.reward_referrer(db)

    # زيادة عدد الإحالات للمحيل
    referrer = db.query(User).filter(User.id == referred_by).first()
    if referrer:
        referrer.increase_referrals()
        db.commit()

# استرجاع النقاط للمستخدم
def get_user_points(db, telegram_id):
    db_user = db.query(User).filter(User.telegram_id == telegram_id).first()
    return db_user.points if db_user else 0

# استرجاع أفضل 10 لاعبين
def get_top_players(db):
    return db.query(User).order_by(User.points.desc()).limit(10).all()

# استرجاع أفضل 10 إحالات
def get_top_referrals(db):
    return db.query(User).join(Referral, Referral.referred_by == User.id).order_by(User.referrals_count.desc()).limit(10).all()

# مثال على كيفية الاستخدام
if __name__ == "__main__":
    # التأكد من أن الجداول تم إنشاؤها
    init_db()

    # الحصول على الجلسة
    with SessionLocal() as db:
        # إضافة مستخدم جديد
        user = add_user(db, telegram_id=123456789, username="john_doe")

        # إضافة إحالة
        add_referral(db, user_id=user.id, referred_by=1)

        # استرجاع النقاط
        print(f"User {user.username} has {get_user_points(db, 123456789)} points")

        # استرجاع أفضل 10 لاعبين
        top_players = get_top_players(db)
        for i, player in enumerate(top_players):
            print(f"{i+1}. {player.username} - {player.points} points")

        # استرجاع أفضل 10 إحالات
        top_referrals = get_top_referrals(db)
        for i, referrer in enumerate(top_referrals):
            print(f"{i+1}. {referrer.username} - {referrer.referrals_count} referrals")
