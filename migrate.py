from app import app, db

with app.app_context():
    with db.engine.connect() as conn:
        conn.execute(db.text('ALTER TABLE booking DROP COLUMN IF EXISTS flavor'))
        conn.execute(db.text('ALTER TABLE booking DROP COLUMN IF EXISTS size'))
        conn.execute(db.text('ALTER TABLE booking DROP COLUMN IF EXISTS theme'))
        conn.execute(db.text('ALTER TABLE booking DROP COLUMN IF EXISTS layers'))
        conn.execute(db.text('ALTER TABLE booking DROP COLUMN IF EXISTS motif_color'))
        conn.execute(db.text('ALTER TABLE booking DROP COLUMN IF EXISTS phone'))
        conn.execute(db.text('ALTER TABLE booking DROP COLUMN IF EXISTS cake_message'))
        conn.execute(db.text('ALTER TABLE booking DROP COLUMN IF EXISTS notes'))
        conn.commit()

print("Done! Columns removed from booking table.")