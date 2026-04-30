plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
    // Firebase / Google Sign-In — MUST come after the Android plugin
    id("com.google.gms.google-services")
}

android {
    // Must match the package_name registered in Firebase Console / google-services.json
    namespace = "com.nutrilens.demo"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = "29.0.13599879"

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_11.toString()
    }

    defaultConfig {
        // Package name MUST match Firebase Console → Android app → Package name
        applicationId = "com.nutrilens.demo"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        release {
            // Sign with debug key for now (replace with release keystore for production)
            signingConfig = signingConfigs.getByName("debug")

            // ── Size optimizations ─────────────────────────────────────────
            // Removes unused Dart/Java code (R8 / ProGuard)
            isMinifyEnabled = true
            // Removes unused resources (drawables, strings, etc.)
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        debug {
            // Keep debug builds fast — no shrinking
            isMinifyEnabled = false
            isShrinkResources = false
        }
    }
}

flutter {
    source = "../.."
}
