package brp.runtime;

/** Raised when a UNIQUE decision matches more than one rule. */
public final class MultipleMatchException extends RuntimeException {
  public MultipleMatchException(String decisionId) {
    super("UNIQUE decision matched multiple rules: " + decisionId);
  }
}
