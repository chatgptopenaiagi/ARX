from arx.cli import main
def test_missing_target(capsys):assert main(["inspect","missing-arx-fixture.exe"])==2

