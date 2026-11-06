plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.sakura.assistant"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.sakura.assistant"
        minSdk = 26
        targetSdk = 34
        versionCode = 100
        versionName = "1.0.0"
        // Override per release with -PversionCode=... / -PversionName=... if required.
    }

    // Release signing is supplied only by the developer's private CI/local secrets.
    // Never commit a production keystore or passwords into this repository.
    val releaseStoreFile = providers.gradleProperty("SAKURA_RELEASE_STORE_FILE").orNull
    val releaseStorePassword = providers.gradleProperty("SAKURA_RELEASE_STORE_PASSWORD").orNull
    val releaseKeyAlias = providers.gradleProperty("SAKURA_RELEASE_KEY_ALIAS").orNull
    val releaseKeyPassword = providers.gradleProperty("SAKURA_RELEASE_KEY_PASSWORD").orNull
    if (!releaseStoreFile.isNullOrBlank() && !releaseStorePassword.isNullOrBlank() &&
        !releaseKeyAlias.isNullOrBlank() && !releaseKeyPassword.isNullOrBlank()) {
        signingConfigs {
            create("commercialRelease") {
                storeFile = file(releaseStoreFile)
                storePassword = releaseStorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }

    buildTypes {
        debug {
            manifestPlaceholders["usesCleartextTraffic"] = "true"
        }
        release {
            isMinifyEnabled = false
            manifestPlaceholders["usesCleartextTraffic"] = "false"
            if (!releaseStoreFile.isNullOrBlank() && !releaseStorePassword.isNullOrBlank() &&
                !releaseKeyAlias.isNullOrBlank() && !releaseKeyPassword.isNullOrBlank()) {
                signingConfig = signingConfigs.getByName("commercialRelease")
            }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    // Wake word (offline). Naya SDK naye .ppn ke saath chalta hai, isliye latest version.
    implementation("ai.picovoice:porcupine-android:+")
    // Wake word bina account ke (offline). Picovoice key na ho to yahi chalta hai.
    implementation("com.alphacephei:vosk-android:0.3.47")
    implementation("net.java.dev.jna:jna:5.13.0@aar")
    // Native Google Sign-In for the Android WebView shell (Credential Manager).
    implementation("androidx.credentials:credentials:1.3.0")
    implementation("androidx.credentials:credentials-play-services-auth:1.3.0")
    implementation("com.google.android.libraries.identity.googleid:googleid:1.1.1")
}
