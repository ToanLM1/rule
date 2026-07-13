from brp.generators.contracts import GeneratedArtifact, TargetGenerator


class FixtureGenerator:
    name = "fixture"
    version = "1"

    def supports(self, profile, target):
        return profile == "RULE_IR_V1"

    def generate(self, release_input):
        return [GeneratedArtifact.create("Fixture.java", release_input.envelope.decision_key)]


def test_runtime_generator_contract_and_artifact_hash() -> None:
    generator = FixtureGenerator()
    assert isinstance(generator, TargetGenerator)
    artifact = GeneratedArtifact.create("한글.java", "class 가입 {}\n")
    assert len(artifact.content_hash) == 64
