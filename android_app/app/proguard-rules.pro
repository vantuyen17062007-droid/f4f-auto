# Add project specific ProGuard rules here.
-keepattributes *Annotation*
-keepclassmembers class * {
    @com.google.gson.annotations.SerializedName <fields>;
}

# Giữ nguyên model Gson khi bật minify (isMinifyEnabled = true)
-keep class com.f4f.autorunner.api.** { *; }
-keep class dadb.** { *; }
