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
        versionCode = 1
        versionName = "1.0"
    }

    // Har build ek hi key se sign ho, taaki naya APK purani app ke upar update ho jaye
    // (aur permissions reset na hon). Ye sirf debug key hai, store wali nahi.
    signingConfigs {
        getByName("debug") {
            storeFile = file("sakura-debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
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
}
