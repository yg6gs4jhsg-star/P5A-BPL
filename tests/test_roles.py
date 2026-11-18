import pytest

from app.accounts.roles import compute_base_role, is_admin
from app.models import AdminEmail

STUDENT = ["gg_O365e_Etudiant"]
EXTERNAL = ["gg_O365e_Enseignant_Non_Permanent"]


# Une règle par test.
def test_epf_is_supervisor():
    assert compute_base_role("prof@epf.fr", []) == "encadrant"


def test_epfedu_external_teacher_is_supervisor():
    assert compute_base_role("ext@epfedu.fr", EXTERNAL) == "encadrant"


def test_epfedu_student_is_student():
    assert compute_base_role("eleve@epfedu.fr", STUDENT) == "etudiant"


def test_epfedu_without_known_group_is_refused():
    assert compute_base_role("perso@epfedu.fr", ["autre_groupe"]) is None


def test_other_domain_is_refused():
    assert compute_base_role("x@gmail.com", STUDENT) is None


# Cas à anticiper.
def test_uppercase_and_spaces_ignored():
    assert compute_base_role("  Prof@EPF.FR ", []) == "encadrant"


@pytest.mark.parametrize("groups", [None, []])
def test_missing_groups_treated_as_empty(groups):
    assert compute_base_role("eleve@epfedu.fr", groups) is None


@pytest.mark.parametrize("email", ["x@epf.fr.autre.com", "x@monepf.fr", "x@epfedu.fr.com"])
def test_fake_domains_refused(email):
    assert compute_base_role(email, STUDENT + EXTERNAL) is None


@pytest.mark.parametrize("email", ["epf.fr", "@epf.fr", "", None])
def test_address_without_local_part_refused(email):
    assert compute_base_role(email, STUDENT) is None


# Liste blanche des admins.
def run(app, *args):
    return app.test_cli_runner().invoke(args=["add-admin", *args])


def test_admin_keeps_supervisor_role(app):
    run(app, "admin.test@epf.fr")
    assert is_admin("admin.test@epf.fr")
    assert compute_base_role("admin.test@epf.fr", []) == "encadrant"


def test_whitelisted_but_neither_role_still_refused(app):
    run(app, "perso@epfedu.fr")
    assert is_admin("perso@epfedu.fr")
    assert compute_base_role("perso@epfedu.fr", []) is None


def test_not_whitelisted_is_not_admin(app):
    assert not is_admin("prof@epf.fr")


def test_add_admin_normalizes_address(app):
    assert run(app, "  Admin.Test@EPF.fr ").exit_code == 0
    assert AdminEmail.query.one().email == "admin.test@epf.fr"
    assert is_admin("ADMIN.TEST@epf.fr")


def test_add_admin_refuses_duplicate(app):
    run(app, "admin.test@epf.fr")
    result = run(app, "ADMIN.test@epf.fr")
    assert result.exit_code != 0 and "Déjà" in result.output
    assert AdminEmail.query.count() == 1


def test_add_admin_refuses_value_without_at(app):
    result = run(app, "epf.fr")
    assert result.exit_code != 0 and AdminEmail.query.count() == 0
