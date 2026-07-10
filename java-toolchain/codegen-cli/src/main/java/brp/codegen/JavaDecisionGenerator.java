package brp.codegen;

import brp.runtime.LookupProvider;
import brp.runtime.MultipleMatchException;
import brp.runtime.RuleSupport;
import com.fasterxml.jackson.databind.JsonNode;
import com.squareup.javapoet.ClassName;
import com.squareup.javapoet.CodeBlock;
import com.squareup.javapoet.FieldSpec;
import com.squareup.javapoet.JavaFile;
import com.squareup.javapoet.MethodSpec;
import com.squareup.javapoet.ParameterizedTypeName;
import com.squareup.javapoet.TypeName;
import com.squareup.javapoet.TypeSpec;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import javax.lang.model.element.Modifier;

/** JavaPoet renderer for the complete restricted Rule IR v1 profile. */
public final class JavaDecisionGenerator {
  public String generate(JsonNode content, String packageName, int revision, String contentHash) {
    String decisionId = content.get("decisionId").asText();
    TypeSpec input = record("Input", content.get("inputs"));
    TypeSpec output = record("Output", content.get("outputs"));
    MethodSpec evaluate = evaluate(content);
    TypeSpec generated =
        TypeSpec.classBuilder(className(decisionId))
            .addModifiers(Modifier.PUBLIC, Modifier.FINAL)
            .addJavadoc(
                "Generated from $L revision $L, content $L. Do not edit.\n",
                decisionId,
                revision,
                contentHash)
            .addType(input)
            .addType(output)
            .addMethod(evaluate)
            .build();
    return JavaFile.builder(packageName, generated)
        .indent("  ")
        .skipJavaLangImports(true)
        .build()
        .toString();
  }

  private TypeSpec record(String name, JsonNode fields) {
    TypeSpec.Builder builder =
        TypeSpec.classBuilder(name).addModifiers(Modifier.PUBLIC, Modifier.STATIC, Modifier.FINAL);
    MethodSpec.Builder constructor = MethodSpec.constructorBuilder().addModifiers(Modifier.PUBLIC);
    for (JsonNode field : fields) {
      String fieldName = field.get("name").asText();
      TypeName type = javaType(field.get("type").asText());
      builder.addField(
          FieldSpec.builder(type, fieldName, Modifier.PRIVATE, Modifier.FINAL).build());
      constructor.addParameter(type, fieldName).addStatement("this.$L = $L", fieldName, fieldName);
      builder.addMethod(
          MethodSpec.methodBuilder(fieldName)
              .addModifiers(Modifier.PUBLIC)
              .returns(type)
              .addStatement("return $L", fieldName)
              .build());
    }
    return builder.addMethod(constructor.build()).build();
  }

  private MethodSpec evaluate(JsonNode content) {
    boolean collect = content.get("hitPolicy").asText().equals("COLLECT");
    TypeName returnType =
        collect
            ? ParameterizedTypeName.get(ClassName.get(List.class), ClassName.bestGuess("Output"))
            : ClassName.bestGuess("Output");
    MethodSpec.Builder method =
        MethodSpec.methodBuilder("evaluate")
            .addModifiers(Modifier.PUBLIC, Modifier.STATIC)
            .returns(returnType)
            .addParameter(ClassName.bestGuess("Input"), "input")
            .addParameter(LookupProvider.class, "lookup");
    if (collect)
      method.addStatement("$T<Output> matches = new $T<>()", List.class, ArrayList.class);
    else if (content.get("hitPolicy").asText().equals("UNIQUE"))
      method.addStatement("Output match = null");
    for (JsonNode rule : content.get("rules")) {
      method.beginControlFlow("if ($L)", group(rule.get("when")));
      CodeBlock output = output(rule.get("then"), content.get("outputs"));
      if (collect) method.addStatement("matches.add($L)", output);
      else if (content.get("hitPolicy").asText().equals("UNIQUE")) {
        method
            .beginControlFlow("if (match != null)")
            .addStatement(
                "throw new $T($S)",
                MultipleMatchException.class,
                content.get("decisionId").asText())
            .endControlFlow();
        method.addStatement("match = $L", output);
      } else method.addStatement("return $L", output);
      method.endControlFlow();
    }
    if (collect) method.addStatement("return $T.copyOf(matches)", List.class);
    else if (content.get("hitPolicy").asText().equals("UNIQUE"))
      method.addStatement("return match != null ? match : $L", defaults(content));
    else method.addStatement("return $L", defaults(content));
    return method.build();
  }

  private CodeBlock group(JsonNode group) {
    JsonNode children = group.has("all") ? group.get("all") : group.get("any");
    String join = group.has("all") ? " && " : " || ";
    CodeBlock.Builder block = CodeBlock.builder().add("(");
    for (int i = 0; i < children.size(); i++) {
      if (i > 0) block.add(join);
      block.add(
          "$L",
          children.get(i).has("operator") ? condition(children.get(i)) : group(children.get(i)));
    }
    return block.add(")").build();
  }

  private CodeBlock condition(JsonNode node) {
    CodeBlock left = operand(node.get("left"));
    String operator = node.get("operator").asText();
    if (operator.equals("EXISTS")) return CodeBlock.of("$L != null", left);
    CodeBlock right = operand(node.get("right"));
    return switch (operator) {
      case "EQ" -> CodeBlock.of("$T.eq($L, $L)", RuleSupport.class, left, right);
      case "NE" -> CodeBlock.of("!$T.eq($L, $L)", RuleSupport.class, left, right);
      case "GT" -> CodeBlock.of("$T.compare($L, $L) > 0", RuleSupport.class, left, right);
      case "GTE" -> CodeBlock.of("$T.compare($L, $L) >= 0", RuleSupport.class, left, right);
      case "LT" -> CodeBlock.of("$T.compare($L, $L) < 0", RuleSupport.class, left, right);
      case "LTE" -> CodeBlock.of("$T.compare($L, $L) <= 0", RuleSupport.class, left, right);
      case "IN" -> CodeBlock.of("$T.contains($L, $L)", RuleSupport.class, right, left);
      case "NOT_IN" -> CodeBlock.of("!$T.contains($L, $L)", RuleSupport.class, right, left);
      case "BETWEEN" ->
          CodeBlock.of(
              "$T.compare($L, $L.get(0)) >= 0 && $T.compare($L, $L.get(1)) <= 0",
              RuleSupport.class,
              left,
              right,
              RuleSupport.class,
              left,
              right);
      case "STARTS_WITH" -> CodeBlock.of("$T.startsWith($L, $L)", RuleSupport.class, left, right);
      default -> throw new IllegalArgumentException("Unsupported operator " + operator);
    };
  }

  private CodeBlock operand(JsonNode operand) {
    return switch (operand.get("kind").asText()) {
      case "INPUT" -> CodeBlock.of("input.$L()", operand.get("name").asText());
      case "LITERAL" -> literal(operand.get("value"));
      case "LOOKUP_FIELD" ->
          CodeBlock.of(
              "lookup.lookup($S, $L).get($S)",
              operand.get("lookup").asText(),
              keys(operand.get("keys")),
              operand.get("field").asText());
      default -> throw new IllegalArgumentException("Unsupported operand");
    };
  }

  private CodeBlock keys(JsonNode keys) {
    CodeBlock.Builder block = CodeBlock.builder().add("$T.of(", Map.class);
    int index = 0;
    for (var fields = keys.fields(); fields.hasNext(); ) {
      var field = fields.next();
      if (index++ > 0) block.add(", ");
      block.add("$S, $L", field.getKey(), operand(field.getValue()));
    }
    return block.add(")").build();
  }

  private CodeBlock output(JsonNode actions, JsonNode outputs) {
    CodeBlock.Builder block = CodeBlock.builder().add("new Output(");
    for (int i = 0; i < outputs.size(); i++) {
      if (i > 0) block.add(", ");
      String name = outputs.get(i).get("name").asText();
      JsonNode value = null;
      for (JsonNode action : actions)
        if (action.get("output").asText().equals(name)) value = action.get("value");
      block.add("$L", literal(value));
    }
    return block.add(")").build();
  }

  private CodeBlock defaults(JsonNode content) {
    CodeBlock.Builder block = CodeBlock.builder().add("new Output(");
    for (int i = 0; i < content.get("outputs").size(); i++) {
      if (i > 0) block.add(", ");
      block.add(
          "$L",
          literal(
              content
                  .get("defaultOutput")
                  .get(content.get("outputs").get(i).get("name").asText())));
    }
    return block.add(")").build();
  }

  private CodeBlock literal(JsonNode value) {
    if (value.isArray()) {
      CodeBlock.Builder block = CodeBlock.builder().add("$T.of(", List.class);
      for (int i = 0; i < value.size(); i++) {
        if (i > 0) block.add(", ");
        block.add("$L", literal(value.get(i)));
      }
      return block.add(")").build();
    }
    if (value.isTextual()) return CodeBlock.of("$S", value.asText());
    if (value.isBoolean()) return CodeBlock.of("$L", value.asBoolean());
    if (value.isIntegralNumber()) return CodeBlock.of("$L", value.asInt());
    return CodeBlock.of("new $T($S)", BigDecimal.class, value.asText());
  }

  private TypeName javaType(String type) {
    return switch (type) {
      case "boolean" -> ClassName.get(Boolean.class);
      case "integer" -> ClassName.get(Integer.class);
      case "decimal" -> ClassName.get(BigDecimal.class);
      case "date" -> ClassName.get(LocalDate.class);
      default -> ClassName.get(String.class);
    };
  }

  public static String className(String decisionId) {
    StringBuilder result = new StringBuilder();
    for (String part : decisionId.split("_"))
      result.append(part.substring(0, 1).toUpperCase(Locale.ROOT)).append(part.substring(1));
    return result.append("Decision").toString();
  }
}
