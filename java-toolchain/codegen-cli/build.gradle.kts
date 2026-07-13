plugins {
    application
}

dependencies {
    implementation(project(":brp-rules-runtime"))
    implementation("com.squareup:javapoet:1.13.0")
    implementation("com.fasterxml.jackson.core:jackson-databind:2.17.2")
}

application {
    mainClass.set("brp.codegen.Main")
}
