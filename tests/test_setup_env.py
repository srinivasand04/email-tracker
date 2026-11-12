from ingest.setup_env import classify, missing, read_env, set_env_value


def test_classify_recognises_each_setting():
    assert classify(" postgresql://u:p@host.neon.tech/db?sslmode=require\n") == (
        "DATABASE_URL",
        "postgresql://u:p@host.neon.tech/db?sslmode=require",
    )
    assert classify("psql 'postgresql://u:p@host/db?sslmode=require'") == (
        "DATABASE_URL",
        "postgresql://u:p@host/db?sslmode=require",
    )
    assert classify("123-abc.apps.googleusercontent.com")[0] == "GOOGLE_CLIENT_ID"
    assert classify("GOCSPX-abc_DEF-123")[0] == "GOOGLE_CLIENT_SECRET"


def test_classify_ignores_everything_else():
    assert classify("hello world") is None
    assert classify("") is None
    assert classify("https://example.com") is None


def test_set_env_value_replaces_in_place_and_keeps_other_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# comment\nDATABASE_URL=old\nGOOGLE_CLIENT_ID=\nINITIAL_SYNC_DAYS=14\n", encoding="utf-8")

    set_env_value(env, "DATABASE_URL", "postgresql://new")
    set_env_value(env, "GOOGLE_CLIENT_SECRET", "GOCSPX-x")

    assert env.read_text(encoding="utf-8") == (
        "# comment\nDATABASE_URL=postgresql://new\nGOOGLE_CLIENT_ID=\nINITIAL_SYNC_DAYS=14\n"
        "GOOGLE_CLIENT_SECRET=GOCSPX-x\n"
    )
    assert read_env(env)["INITIAL_SYNC_DAYS"] == "14"


def test_missing_treats_placeholder_and_blank_as_missing(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require\n"
        "GOOGLE_CLIENT_ID=\nGOOGLE_CLIENT_SECRET=GOCSPX-x\n",
        encoding="utf-8",
    )
    assert missing(env) == ["DATABASE_URL", "GOOGLE_CLIENT_ID"]
