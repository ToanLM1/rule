package legacy.model;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

public final class EnrollmentResult {
  private boolean eligible = true;
  private String reasonCode = "ELIGIBLE";
  private int premiumLoadingPct;
  private final Set<String> requiredDocs = new LinkedHashSet<>();

  public boolean eligible() {
    return eligible;
  }

  public String reasonCode() {
    return reasonCode;
  }

  public int premiumLoadingPct() {
    return premiumLoadingPct;
  }

  public List<String> requiredDocs() {
    return new ArrayList<>(requiredDocs);
  }

  public void reject(String reason) {
    eligible = false;
    reasonCode = reason;
  }

  public void addPremiumLoading(int percentage) {
    premiumLoadingPct += percentage;
  }

  public void addRequiredDoc(String documentCode) {
    requiredDocs.add(documentCode);
  }
}
