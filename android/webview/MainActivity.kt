package dev.fennec.webview

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity

/**
 * Minimal scaffold: loads a local/LAN Fennec server in a WebView.
 * Requires Android SDK + Gradle + androidx.appcompat to build (not shipped here).
 * Add <uses-permission android:name="android.permission.INTERNET"/> to the manifest
 * and allow cleartext for 127.0.0.1 via a network-security-config if needed.
 */
class MainActivity : AppCompatActivity() {
    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val webView = WebView(this)
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        webView.webViewClient = WebViewClient()
        setContentView(webView)
        // Point at the Termux-run core-supervised PWA/API on 8787 or a LAN host;
        // FENNEC_URL overrides. Rust auxiliary/chat on 8788 and the engine on
        // 8184 are not UI front doors.
        val url = System.getenv("FENNEC_URL") ?: "http://127.0.0.1:8787"
        webView.loadUrl(url)
    }
}