import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_user_can_be_created_with_each_role():
    inspector = User.objects.create_user(
        username="ins1", password="pw-does-not-matter", role=User.Role.INSPECTOR
    )
    owner = User.objects.create_user(
        username="own1", password="pw-does-not-matter", role=User.Role.OWNER
    )

    inspector.refresh_from_db()
    owner.refresh_from_db()

    assert inspector.role == "INSPECTOR"
    assert owner.role == "OWNER"
