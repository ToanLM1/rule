package brp.codegen;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Files;
import java.nio.file.Path;

/** CLI for deterministic Java source generation. */
public final class Main {
  private Main() {}

  public static void main(String[] args) throws Exception {
    if (args.length != 2) {
      System.out.println("usage: brp-codegen <release-input.json> <output-directory>");
      return;
    }
    JsonNode release = new ObjectMapper().readTree(Path.of(args[0]).toFile());
    String packageName = release.at("/target/javaPackage").asText();
    JsonNode content = release.get("content");
    String source =
        new JavaDecisionGenerator()
            .generate(
                content,
                packageName,
                release.at("/envelope/revision").asInt(),
                release.at("/envelope/contentHash").asText());
    String className = JavaDecisionGenerator.className(content.get("decisionId").asText());
    Path target =
        Path.of(args[1]).resolve(packageName.replace('.', '/')).resolve(className + ".java");
    Files.createDirectories(target.getParent());
    Files.writeString(target, source);
  }
}
