from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import os
import logging

# إعداد التسجيل للخطأ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# رابط قاعدة البيانات من متغير البيئة
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///database.db")

# إعدادات اتصال أكثر قوة
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String(255), nullable=True)
    points = Column(Integer, default=0, nullable=False)
    referrals_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    referrals_made = relationship(
        "Referral",
        foreign_keys="[Referral.referred_by]",
        back_populates="referrer",
        cascade="all, delete-orphan"
    )
    referrals_received = relationship(
        "Referral",
        foreign_keys="[Referral.user_id]",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, points={self.points})>"

    def increase_points(self, points: int, session=None):
        try:
            self.points += points
            if session:
                session.commit()
            logger.info(f"Increased points for user {self.id} by {points}")
        except Exception as e:
            logger.error(f"Error increasing points: {e}")
            if session:
                session.rollback()
            raise

    def increase_referrals(self, session=None):
        try:
            self.referrals_count += 1
            if session:
                session.commit()
            logger.info(f"Increased referrals count for user {self.id}")
        except Exception as e:
            logger.error(f"Error increasing referrals: {e}")
            if session:
                session.rollback()
            raise

class Referral(Base):
    __tablename__ = 'referrals'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    referred_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    date = Column(DateTime, default=datetime.utcnow, nullable=False)
    reward_points = Column(Integer, default=100, nullable=False)

    user = relationship("User", foreign_keys=[user_id], back_populates="referrals_received")
    referrer = relationship("User", foreign_keys=[referred_by], back_populates="referrals_made")

    def __repr__(self):
        return f"<Referral(id={self.id}, user={self.user_id}, referrer={self.referred_by})>"

    def reward_referrer(self, session):
        try:
            referrer_user = session.query(User).filter(User.id == self.referred_by).first()
            if referrer_user:
                referrer_user.increase_points(self.reward_points, session)
                referrer_user.increase_referrals(session)
                logger.info(f"Rewarded referrer {referrer_user.username} with {self.reward_points} points")
            else:
                logger.warning(f"Referrer user {self.referred_by} not found")
        except Exception as e:
            logger.error(f"Error rewarding referrer: {e}")
            raise

def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def add_user(db, telegram_id: int, username: str = None) -> User:
    try:
        db_user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not db_user:
            db_user = User(
                telegram_id=telegram_id,
                username=username,
                points=0,
                referrals_count=0
            )
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            logger.info(f"Added new user: {username} (ID: {telegram_id})")
        else:
            if username and db_user.username != username:
                db_user.username = username
                db.commit()
                db.refresh(db_user)
                logger.info(f"Updated username for user {telegram_id}")
        return db_user
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding/updating user: {e}")
        raise

def add_referral(db, user_id: int, referred_by: int) -> Referral:
    try:
        # تجنب الإحالة الذاتية
        if user_id == referred_by:
            raise ValueError("User cannot refer themselves")

        existing = db.query(Referral).filter(
            Referral.user_id == user_id,
            Referral.referred_by == referred_by
        ).first()
        
        if existing:
            logger.warning(f"Referral already exists: User {user_id} referred by {referred_by}")
            return existing
            
        db_referral = Referral(user_id=user_id, referred_by=referred_by)
        db.add(db_referral)
        db.commit()
        db.refresh(db_referral)
        db_referral.reward_referrer(db)
        
        logger.info(f"Added new referral: User {user_id} referred by {referred_by}")
        return db_referral
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding referral: {e}")
        raise

def get_user(db, telegram_id: int) -> User:
    try:
        return db.query(User).filter(User.telegram_id == telegram_id).first()
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        raise

def get_user_points(db, telegram_id: int) -> int:
    try:
        user = get_user(db, telegram_id)
        return user.points if user else 0
    except Exception as e:
        logger.error(f"Error getting user points: {e}")
        raise

def get_top_players(db, limit: int = 10):
    try:
        return db.query(User).order_by(User.points.desc()).limit(limit).all()
    except Exception as e:
        logger.error(f"Error getting top players: {e}")
        raise

def get_top_referrers(db, limit: int = 10):
    try:
        return db.query(User).order_by(User.referrals_count.desc()).limit(limit).all()
    except Exception as e:
        logger.error(f"Error getting top referrers: {e}")
        raise

def update_user_points(db, telegram_id: int, points: int):
    try:
        user = get_user(db, telegram_id)
        if user:
            user.increase_points(points, db)
            db.commit()
            return True
        return False
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating user points: {e}")
        raise

# تهيئة قاعدة البيانات عند الاستيراد
init_db()
