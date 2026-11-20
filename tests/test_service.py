from pathlib import Path

import pytest
from sqlalchemy.orm.attributes import set_committed_value

from app.models import HistoryEvent, Project, db
from app.projects import service
from app.projects.service import ProjectError, change_status, create_project
from tests.conftest import person


@pytest.fixture
def people(app):
    return {
        "owner": person("owner"),
        "encadrant": person("encadrant", "encadrant"),
        "admin": person("admin", "encadrant", admin=True),
        "autre": person("autre"),
    }


@pytest.fixture
def project(people):
    return create_project(people["owner"], "Drone autonome", people["encadrant"])


def statuses(project):
    return [(e.old_status, e.new_status) for e in project.history]


# Création.
def test_create_project(app, people, project):
    assert (project.slug, project.status, project.supervisor) == ("drone-autonome", "brouillon", people["encadrant"])
    assert [(m.account, m.role) for m in project.members] == [(people["owner"], "owner")]
    assert statuses(project) == [(None, "brouillon")]
    for subdir in ("draft", "published", "files"):
        assert (Path(app.config["CONTENT_DIR"]) / "projects" / project.uuid / subdir).is_dir()


def test_same_title_gets_numbered_slug(people, project):
    project.deleted_at = db.func.now()  # la corbeille compte aussi
    assert create_project(people["owner"], "Drone autonome").slug == "drone-autonome-2"
    assert create_project(people["owner"], "Drone autonome").slug == "drone-autonome-3"


@pytest.mark.parametrize("title, slug", [("  Éco-Énergie à l'EPF ! ", "eco-energie-a-l-epf"), ("2026 !!", "projet")])
def test_slug_from_title(people, title, slug):
    assert create_project(people["owner"], title).slug == slug


@pytest.mark.parametrize("title", ["", "   ", "x" * 201])
def test_bad_title_refused(people, title):
    with pytest.raises(ProjectError):
        create_project(people["owner"], title)


def test_only_students_create(people):
    with pytest.raises(ProjectError):
        create_project(people["encadrant"], "Projet")
    with pytest.raises(ProjectError):
        create_project(None, "Projet")


def test_supervisor_must_be_a_teacher(people):
    with pytest.raises(ProjectError):
        create_project(people["owner"], "Projet", people["autre"])
    assert Project.query.count() == 0


# Une transition autorisée par ligne du § 3.
PATH = [
    ("owner", "submit", "en_relecture"),
    ("encadrant", "request_changes", "brouillon"),
    ("owner", "submit", "en_relecture"),
    ("admin", "publish", "publie"),
    ("owner", "request_reedition", "reedition_demandee"),
    ("encadrant", "refuse_reedition", "publie"),
    ("owner", "request_reedition", "reedition_demandee"),
    ("admin", "accept_reedition", "brouillon"),
]


def test_lifecycle(people, project):
    for who, action, expected in PATH:
        change_status(people[who], project, action, message=f"{action} !")
        assert project.status == expected, action
    assert project.history[-1].message == "accept_reedition !"
    assert len(project.history) == 1 + len(PATH)


def test_unpublish_and_republish(people, project):
    change_status(people["owner"], project, "submit")
    change_status(people["encadrant"], project, "publish")
    first = project.first_published_at
    change_status(people["encadrant"], project, "unpublish")
    assert project.status == "retire"
    change_status(people["encadrant"], project, "publish")
    assert project.status == "publie" and project.first_published_at == first  # première publication seulement


def test_first_published_at_filled_on_first_publication(people, project):
    change_status(people["owner"], project, "submit")
    assert project.first_published_at is None
    change_status(people["encadrant"], project, "publish")
    assert project.first_published_at is not None


# Refus.
def test_wrong_role_refused(people, project):
    with pytest.raises(ProjectError, match="droit"):
        change_status(people["encadrant"], project, "submit")
    change_status(people["owner"], project, "submit")
    with pytest.raises(ProjectError, match="droit"):
        change_status(people["owner"], project, "publish")
    assert statuses(project)[-1] == ("brouillon", "en_relecture")


def test_wrong_status_refused(people, project):
    with pytest.raises(ProjectError):
        change_status(people["encadrant"], project, "publish")


def test_second_click_refused(people, project):
    change_status(people["owner"], project, "submit")
    with pytest.raises(ProjectError, match="déjà changé"):
        change_status(people["owner"], project, "submit")
    assert len(project.history) == 2


def test_two_simultaneous_reads_of_same_status(people, project):
    change_status(people["owner"], project, "submit")
    set_committed_value(project, "status", "brouillon")  # l'autre lecture a encore vu « Brouillon »
    with pytest.raises(ProjectError, match="déjà changé"):
        change_status(people["owner"], project, "submit")
    db.session.expire_all()
    assert project.status == "en_relecture" and len(project.history) == 2


def test_submit_without_supervisor_refused(people):
    project = create_project(people["owner"], "Sans encadrant")
    with pytest.raises(ProjectError, match="attendez"):
        change_status(people["owner"], project, "submit")


def test_failure_cancels_status_and_history(people, project, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("panne")
    monkeypatch.setattr(service, "HistoryEvent", broken)
    with pytest.raises(RuntimeError):
        change_status(people["owner"], project, "submit")
    db.session.expire_all()
    assert project.status == "brouillon" and HistoryEvent.query.count() == 1


# Encadrant, corbeille.
def test_assign_supervisor(people):
    project = create_project(people["owner"], "Projet")
    with pytest.raises(ProjectError):
        service.assign_supervisor(people["owner"], project, people["encadrant"])
    with pytest.raises(ProjectError):
        service.assign_supervisor(people["admin"], project, people["autre"])
    service.assign_supervisor(people["admin"], project, people["encadrant"])
    assert project.supervisor == people["encadrant"]


def test_delete_and_restore(people, project):
    service.delete_project(people["owner"], project)
    assert project.deleted_at is not None
    assert statuses(project)[-1] == ("brouillon", "brouillon")
    with pytest.raises(ProjectError):
        service.restore_project(people["owner"], project)
    service.restore_project(people["admin"], project)
    assert project.deleted_at is None


def test_owner_cannot_delete_published_project(people, project):
    change_status(people["owner"], project, "submit")
    change_status(people["encadrant"], project, "publish")
    with pytest.raises(ProjectError):
        service.delete_project(people["owner"], project)
    service.delete_project(people["admin"], project)
