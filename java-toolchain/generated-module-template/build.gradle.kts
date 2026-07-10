plugins { java }

// Copied into a target repository by generation orchestration. Generated sources and
// golden tests are written below src/generated/java and src/generatedTest/java.
sourceSets {
    main { java.srcDir("src/generated/java") }
    test { java.srcDir("src/generatedTest/java") }
}

dependencies { implementation(project(":brp-rules-runtime")) }
