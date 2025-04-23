import sqlite3
from datetime import datetime
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

class ReferralSystem:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def get_db_connection(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            yield conn
        except sqlite3.Error as e:
            logger.error(f"خطأ في الاتصال بقاعدة البيانات: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def init_db(self):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referred_by INTEGER NOT NULL,
                    referred_user_id INTEGER NOT NULL,
                    referral_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(referred_by, referred_user_id),
                    FOREIGN KEY (referred_by) REFERENCES users(user_id),
                    FOREIGN KEY (referred_user_id) REFERENCES users(user_id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_referred_by ON referrals(referred_by)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_referred_user ON referrals(referred_user_id)")
            conn.commit()

    def add_referral(self, referrer_id: int, referred_user_id: int) -> bool:
        try:
            with self.get_db_connection() as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO referrals (referred_by, referred_user_id)
                    VALUES (?, ?)
                """, (referrer_id, referred_user_id))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"فشل في تسجيل الإحالة: {e}")
            return False

    def get_referral_count(self, user_id: int) -> int:
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) as count FROM referrals 
                    WHERE referred_by = ?
                """, (user_id,))
                return cursor.fetchone()['count']
        except sqlite3.Error as e:
            logger.error(f"فشل في جلب عدد الإحالات: {e}")
            return 0

    def get_leaderboard(self, limit: int = 10):
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        u.user_id,
                        u.username,
                        u.first_name,
                        u.last_name,
                        COUNT(r.id) as referral_count
                    FROM users u
                    LEFT JOIN referrals r ON u.user_id = r.referred_by
                    GROUP BY u.user_id
                    ORDER BY referral_count DESC
                    LIMIT ?
                """, (limit,))
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"فشل في جلب لوحة المتصدرين: {e}")
            return []

    def get_user_display_name(self, user_id: int) -> str:
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT user_id, username, first_name, last_name 
                    FROM users WHERE user_id = ?
                """, (user_id,))
                user = cursor.fetchone()
                if user:
                    return self._format_display_name(user)
        except sqlite3.Error as e:
            logger.error(f"فشل في جلب اسم المستخدم: {e}")
        return f"المستخدم {user_id}"

    def _format_display_name(self, user_row) -> str:
        name_parts = []
        if user_row['first_name']:
            name_parts.append(user_row['first_name'])
        if user_row['last_name']:
            name_parts.append(user_row['last_name'])
        
        full_name = ' '.join(name_parts) if name_parts else None
        
        if user_row['username']:
            if full_name:
                return f"@{user_row['username']} ({full_name})"
            return f"@{user_row['username']}"
        elif full_name:
            return full_name
        return f"المستخدم {user_row['user_id']}"
