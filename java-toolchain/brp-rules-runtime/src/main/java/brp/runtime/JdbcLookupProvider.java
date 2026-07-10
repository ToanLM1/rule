package brp.runtime;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.SQLException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

/** Prepared-statement JDBC lookup provider with configuration-time identifier validation. */
public final class JdbcLookupProvider implements LookupProvider {
  public record Definition(String table, List<String> keys, List<String> outputs) {}

  private static final Pattern IDENTIFIER = Pattern.compile("[A-Za-z_][A-Za-z0-9_]*");
  private final Connection connection;
  private final Map<String, Definition> definitions;

  public JdbcLookupProvider(Connection connection, Map<String, Definition> definitions) {
    this.connection = connection;
    this.definitions = Map.copyOf(definitions);
    definitions.values().forEach(JdbcLookupProvider::validate);
  }

  @Override
  public Map<String, Object> lookup(String name, Map<String, Object> keys) {
    Definition definition = definitions.get(name);
    if (definition == null || !keys.keySet().equals(new java.util.HashSet<>(definition.keys())))
      return Map.of();
    String columns =
        definition.outputs().stream()
            .map(JdbcLookupProvider::quote)
            .collect(java.util.stream.Collectors.joining(","));
    String predicates =
        definition.keys().stream()
            .map(key -> quote(key) + " = ?")
            .collect(java.util.stream.Collectors.joining(" AND "));
    String query =
        "SELECT " + columns + " FROM " + quote(definition.table()) + " WHERE " + predicates;
    try (PreparedStatement statement = connection.prepareStatement(query)) {
      int index = 1;
      for (String key : definition.keys()) statement.setObject(index++, keys.get(key));
      try (ResultSet rows = statement.executeQuery()) {
        if (!rows.next()) return Map.of();
        ResultSetMetaData metadata = rows.getMetaData();
        Map<String, Object> result = new LinkedHashMap<>();
        for (int column = 1; column <= metadata.getColumnCount(); column++)
          result.put(metadata.getColumnLabel(column), rows.getObject(column));
        return Map.copyOf(result);
      }
    } catch (SQLException exception) {
      throw new IllegalStateException("Lookup execution failed for " + name, exception);
    }
  }

  private static void validate(Definition definition) {
    if (!IDENTIFIER.matcher(definition.table()).matches())
      throw new IllegalArgumentException("Invalid table identifier");
    definition.keys().forEach(JdbcLookupProvider::requireIdentifier);
    definition.outputs().forEach(JdbcLookupProvider::requireIdentifier);
  }

  private static void requireIdentifier(String value) {
    if (!IDENTIFIER.matcher(value).matches())
      throw new IllegalArgumentException("Invalid column identifier");
  }

  private static String quote(String value) {
    return "\"" + value + "\"";
  }
}
