import pytest

from app import create_app


@pytest.fixture
def client():
    return create_app().test_client()


def test_home_responds(client):
    assert client.get("/").status_code == 200


def test_unknown_url_is_404(client):
    assert client.get("/adresse-inconnue").status_code == 404
