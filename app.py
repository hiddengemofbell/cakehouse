from modules import create_app, db

app = create_app()

with app.app_context():
    db.create_all()

@app.cli.command('make-admin')
def make_admin():
    """Promote a user to admin by email via CLI: flask make-admin <email>"""
    import click
    from modules.models import User
    email = click.prompt('Enter user email to promote to admin')
    user = User.query.filter_by(email=email.strip()).first()
    if not user:
        click.echo(f"Error: User with email '{email}' was not found.")
        return
    user.role = 'admin'
    db.session.commit()
    click.echo(f"Success! {user.name} ({user.email}) is now an admin.")

if __name__ == '__main__':
    app.run(debug=True)