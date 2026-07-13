@main def exec(cpgFile: String) = {
  importCpg(cpgFile)
  val methodCount = cpg.method.size
  val targetCount = cpg.method
    .nameExact("evaluate")
    .filename(".*EnrollmentValidator.java")
    .size
  println(s"BRP_METHOD_COUNT=$methodCount")
  println(s"BRP_TARGET_COUNT=$targetCount")
  if (methodCount <= 0 || targetCount <= 0) {
    throw new RuntimeException("EnrollmentValidator.evaluate was not found")
  }
}
