import pytest

from app.authorization.rules import RULES, can
from app.models import Account, AdminEmail, Member, Project, db, utcnow

# Matrice des droits (§ 2.2) : action -> (statut du projet testé, droits V C Co O E A).
# V visiteur, C client, Co collabo, O owner, E encadrant du projet, A admin. None = sans projet.
# create_project : « tout étudiant connecté » ; le Collabo de test est étudiant, le Client et l'admin non.
MATRIX = {
    "view_published":     ("publie",             "111111"),
    "read_project":       ("brouillon",          "011111"),
    "create_project":     (None,                 "001100"),
    "manage_members":     ("brouillon",          "000101"),
    "edit_draft":         ("brouillon",          "001111"),
    "submit":             ("brouillon",          "000100"),
    "request_changes":    ("en_relecture",       "000011"),
    "publish":            ("en_relecture",       "000011"),
    "unpublish":          ("publie",             "000011"),
    "request_reedition":  ("publie",             "000100"),
    "answer_reedition":   ("reedition_demandee", "000011"),
    "feature_project":    ("publie",             "000011"),
    "comment":            ("brouillon",          "010000"),
    "read_comments":      ("brouillon",          "011111"),
    "delete_project":     ("brouillon",          "000101"),
    "restore_project":    ("brouillon",          "000001"),
    "transfer_ownership": ("brouillon",          "000101"),
    "assign_supervisor":  ("brouillon",          "000001"),
    "admin_site":         (None,                 "000001"),
}
COLUMNS = ("visiteur", "client", "collabo", "owner", "encadrant", "admin")


def person(name, base_role="etudiant", admin=False):
    account = Account(oid=name, email=f"{name}@epf.fr", name=name, base_role=base_role)
    db.session.add(account)
    if admin:
        db.session.add(AdminEmail(email=account.email))
    return account


@pytest.fixture
def team(app):
    """Un projet et une personne par colonne de la matrice (le visiteur n'est pas connecté)."""
    people = {
        "visiteur": None,
        "client": person("client", "encadrant"),
        "collabo": person("collabo"),
        "owner": person("owner"),
        "encadrant": person("encadrant", "encadrant"),
        "admin": person("admin", "encadrant", admin=True),
        "autre_encadrant": person("autre", "encadrant"),
        "exterieur": person("exterieur"),
    }
    project = Project(slug="drone", title="Drone", supervisor=people["encadrant"])
    db.session.add(project)
    for role in ("client", "collabo", "owner"):
        db.session.add(Member(project=project, account=people[role], role=role))
    db.session.commit()
    return project, people


@pytest.mark.parametrize("action", MATRIX)
def test_matrix(team, action):
    project, people = team
    status, expected = MATRIX[action]
    if status:
        project.status = status
    for column, allowed in zip(COLUMNS, expected):
        assert can(people[column], action, project if status else None) is (allowed == "1"), column


def test_every_rule_is_in_matrix():
    assert set(RULES) == set(MATRIX)


def test_unknown_action_raises(team):
    with pytest.raises(KeyError):
        can(None, "voler")


def test_draft_locked_after_submission_even_for_admin(team):
    project, people = team
    project.status = "en_relecture"
    assert not any(can(people[r], "edit_draft", project) for r in COLUMNS)


def test_old_version_public_during_reedition(team):
    project, people = team
    project.first_published_at = utcnow()
    for status in ("reedition_demandee", "brouillon", "en_relecture"):
        project.status = status
        assert can(None, "view_published", project), status


def test_never_published_draft_not_public(team):
    project, _ = team
    assert not can(None, "view_published", project)


def test_withdrawn_project_not_public(team):
    project, people = team
    project.status, project.first_published_at = "retire", utcnow()
    assert not can(None, "view_published", project)
    assert can(people["owner"], "read_project", project)


def test_deleted_project_hidden_except_for_admin(team):
    project, people = team
    project.status, project.first_published_at, project.deleted_at = "publie", utcnow(), utcnow()
    for role in ("visiteur", "client", "collabo", "owner", "encadrant"):
        assert not can(people[role], "view_published", project), role
        assert not can(people[role], "read_project", project), role
    assert can(people["admin"], "read_project", project)
    assert can(people["admin"], "restore_project", project)


def test_owner_deletes_only_if_never_published(team):
    project, people = team
    assert can(people["owner"], "delete_project", project)
    project.first_published_at = utcnow()
    assert not can(people["owner"], "delete_project", project)
    assert can(people["admin"], "delete_project", project)


def test_republish_withdrawn_project(team):
    project, people = team
    project.status = "retire"
    assert can(people["encadrant"], "publish", project)
    assert not can(people["owner"], "publish", project)


def test_admin_and_supervisor_cumulate(team):
    project, people = team
    project.supervisor = people["admin"]
    project.status = "en_relecture"
    assert can(people["admin"], "publish", project)
    assert can(people["admin"], "read_comments", project)


def test_admin_and_owner_cumulate(team):
    project, people = team
    db.session.add(AdminEmail(email=people["owner"].email))
    assert can(people["owner"], "submit", project)  # droit d'Owner
    assert can(people["owner"], "assign_supervisor", project)  # droit d'admin


def test_supervisor_of_another_project_is_a_visitor(team):
    project, people = team
    other = people["autre_encadrant"]
    assert not can(other, "read_project", project)
    project.status = "en_relecture"
    assert not can(other, "publish", project)
    project.status = "publie"
    assert can(other, "view_published", project) and not can(other, "feature_project", project)


def test_no_supervisor_only_admin_acts(team):
    project, people = team
    project.supervisor, project.status = None, "en_relecture"
    assert not can(people["encadrant"], "publish", project)
    assert can(people["admin"], "publish", project)


def test_outsider_student_can_create_but_not_read(team):
    project, people = team
    assert can(people["exterieur"], "create_project")
    assert not can(people["exterieur"], "read_project", project)
