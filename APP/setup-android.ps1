# Mezzofy AI - Android Build Setup (Windows)
# Run this from the project root directory (where package.json is)

Write-Host "=== Mezzofy AI - Android Build Setup ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Node.js
Write-Host "Checking Node.js..." -NoNewline
try {
    $nodeVersion = node --version
    Write-Host " OK ($nodeVersion)" -ForegroundColor Green
} catch {
    Write-Host " MISSING" -ForegroundColor Red
    Write-Host "Install Node.js 18+ from https://nodejs.org"
    exit 1
}

# Step 2: Check Java
Write-Host "Checking Java JDK..." -NoNewline
try {
    $javaVersion = java -version 2>&1 | Select-Object -First 1
    Write-Host " OK ($javaVersion)" -ForegroundColor Green
} catch {
    Write-Host " MISSING" -ForegroundColor Red
    Write-Host "Install JDK 17 from https://adoptium.net"
    exit 1
}

# Step 3: Check ANDROID_HOME
Write-Host "Checking ANDROID_HOME..." -NoNewline
if ($env:ANDROID_HOME) {
    Write-Host " OK ($env:ANDROID_HOME)" -ForegroundColor Green
} else {
    $defaultPath = "$env:LOCALAPPDATA\Android\Sdk"
    if (Test-Path $defaultPath) {
        $env:ANDROID_HOME = $defaultPath
        Write-Host " Found at $defaultPath" -ForegroundColor Yellow
        Write-Host "  Add to system env: setx ANDROID_HOME `"$defaultPath`""
    } else {
        Write-Host " NOT SET" -ForegroundColor Red
        Write-Host "  Set ANDROID_HOME to your Android SDK path"
        Write-Host "  Usually: $env:LOCALAPPDATA\Android\Sdk"
        exit 1
    }
}

# Step 4: Install npm dependencies
Write-Host ""
Write-Host "Installing npm dependencies..." -ForegroundColor Cyan
npm install
if ($LASTEXITCODE -ne 0) {
    Write-Host "npm install failed" -ForegroundColor Red
    exit 1
}

# Step 5: Generate Gradle wrapper (if missing)
if (-not (Test-Path "android\gradlew.bat")) {
    Write-Host ""
    Write-Host "Generating Gradle wrapper..." -ForegroundColor Cyan
    Push-Location android
    
    # Use gradle from Android Studio if available
    $studioGradle = "$env:ANDROID_HOME\..\Android Studio\gradle\gradle-8.2\bin\gradle.bat"
    $pathGradle = Get-Command gradle -ErrorAction SilentlyContinue
    
    if (Test-Path $studioGradle) {
        & $studioGradle wrapper --gradle-version 8.3
    } elseif ($pathGradle) {
        gradle wrapper --gradle-version 8.3
    } else {
        Write-Host "Gradle not found. Opening Android Studio to generate wrapper..." -ForegroundColor Yellow
        Write-Host "  1. Open Android Studio"
        Write-Host "  2. File > Open > select the 'android' folder"
        Write-Host "  3. Let it sync (this generates gradlew.bat)"
        Write-Host "  4. Then run: cd android; .\gradlew.bat assembleDebug"
        Pop-Location
        exit 0
    }
    Pop-Location
}

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "To build the APK:" -ForegroundColor Cyan
Write-Host "  cd android"
Write-Host "  .\gradlew.bat assembleDebug"
Write-Host ""
Write-Host "APK will be at:"
Write-Host "  android\app\build\outputs\apk\debug\app-debug.apk"
