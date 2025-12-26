import pytest
from app import app, db, User, Clan, Project

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.session.remove()
            db.drop_all()

def test_user_registration(client):
    response = client.post('/register', data={
        'username': 'testuser',
        'password': 'password123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Account created. Please log in.' in response.data

def test_create_clan(client):
    client.post('/register', data={'username': 'owner', 'password': 'password'}, follow_redirects=True)
    client.post('/login', data={'username': 'owner', 'password': 'password'}, follow_redirects=True)

    response = client.post('/create_clan', data={'clan_name': 'TestClan'}, follow_redirects=True)
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert 'Clan' in html and 'TestClan' in html and 'created!' in html

    with app.app_context():
        clan = Clan.query.filter_by(name='TestClan').first()
        assert clan is not None
        user = User.query.filter_by(username='owner').first()
        assert user.clan_id == clan.id

def test_join_clan(client):
    # Owner creates clan
    client.post('/register', data={'username': 'owner', 'password': 'password'}, follow_redirects=True)
    client.post('/login', data={'username': 'owner', 'password': 'password'}, follow_redirects=True)
    client.post('/create_clan', data={'clan_name': 'TestClan'}, follow_redirects=True)

    client.get('/logout', follow_redirects=True)

    # Member registers and joins
    client.post('/register', data={'username': 'member', 'password': 'password'}, follow_redirects=True)
    client.post('/login', data={'username': 'member', 'password': 'password'}, follow_redirects=True)

    response = client.post('/join_clan', data={'clan_name': 'TestClan'}, follow_redirects=True)
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert 'Joined clan' in html and 'TestClan' in html

    with app.app_context():
        user = User.query.filter_by(username='member').first()
        clan = Clan.query.filter_by(name='TestClan').first()
        assert user.clan_id == clan.id

def test_assign_task_permission(client):
    # 1. Owner creates clan
    client.post('/register', data={'username': 'owner', 'password': 'password'}, follow_redirects=True)
    client.post('/login', data={'username': 'owner', 'password': 'password'}, follow_redirects=True)
    client.post('/create_clan', data={'clan_name': 'TestClan'}, follow_redirects=True)
    client.get('/logout', follow_redirects=True)

    # 2. Member joins clan
    client.post('/register', data={'username': 'member', 'password': 'password'}, follow_redirects=True)
    client.post('/login', data={'username': 'member', 'password': 'password'}, follow_redirects=True)
    client.post('/join_clan', data={'clan_name': 'TestClan'}, follow_redirects=True)
    client.get('/logout', follow_redirects=True)

    # 3. Outsider exists
    client.post('/register', data={'username': 'outsider', 'password': 'password'}, follow_redirects=True)
    client.get('/logout', follow_redirects=True)

    # Test: Owner assigns task to Member (Should succeed)
    client.post('/login', data={'username': 'owner', 'password': 'password'}, follow_redirects=True)

    response = client.post('/dashboard', data={
        'title': 'Clan Task',
        'description': 'Do work',
        'deadline': '2023-12-31',
        'assigned_to': 'member'
    }, follow_redirects=True)

    assert b'Task created!' in response.data

    # Test: Owner assigns task to Outsider (Should fail)
    response = client.post('/dashboard', data={
        'title': 'Illegal Task',
        'description': 'Do work',
        'deadline': '2023-12-31',
        'assigned_to': 'outsider'
    }, follow_redirects=True)

    html = response.data.decode('utf-8')
    assert 'You can only assign tasks to members of your clan.' in html

def test_leave_clan(client):
    client.post('/register', data={'username': 'leaver', 'password': 'password'}, follow_redirects=True)
    client.post('/login', data={'username': 'leaver', 'password': 'password'}, follow_redirects=True)
    client.post('/create_clan', data={'clan_name': 'TempClan'}, follow_redirects=True)

    response = client.post('/leave_clan', follow_redirects=True)
    assert b'You left the clan' in response.data

    with app.app_context():
        user = User.query.filter_by(username='leaver').first()
        assert user.clan_id is None
