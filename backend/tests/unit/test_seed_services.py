"""The seeded service menu matches product-spec.md."""

from app.store import SEED_SERVICES


def test_seed_menu_matches_spec():
    assert SEED_SERVICES == [
        ("Haircut", 30, 150),
        ("Hair Colour", 90, 450),
        ("Root Touch-Up", 60, 300),
        ("Manicure", 45, 200),
        ("Pedicure", 60, 280),
        ("Facial", 60, 350),
    ]


def test_service_names_are_unique():
    names = [name for name, _, _ in SEED_SERVICES]
    assert len(names) == len(set(names))
