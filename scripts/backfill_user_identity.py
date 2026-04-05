from app.clerk_client import clerk
from app.database import SessionLocal
from app import models
from app.identity import populate_user_identity


BATCH_SIZE = 200


def run():
    db = SessionLocal()
    try:
        users = (
            db.query(models.User)
            .order_by(models.User.created_at.asc())
            .all()
        )

        updated = 0
        for user in users:
            try:
                clerk_user = clerk.users.get(user_id=user.clerk_id)
            except Exception:
                continue

            populate_user_identity(
                user,
                clerk_user.first_name,
                clerk_user.last_name,
                clerk_user.image_url if clerk_user.has_image else None,
            )
            updated += 1

            if updated % BATCH_SIZE == 0:
                db.commit()
                print(f"Committed {updated} user identity updates")

        db.commit()
        print(f"Backfill complete. Updated {updated} users.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
