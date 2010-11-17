package com.afg;

import android.app.Activity;
import android.content.Context;
import android.net.ConnectivityManager;
import android.os.Bundle;
import android.webkit.WebView;
import android.widget.TextView;

public class TabHelp extends Activity {
	private WebView webview = null;
    private String current_url = "";
    
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        TextView textview = new TextView(this);
        textview.setText("Loading...");
        setContentView(textview);
        this.setURL("http://afg.echo3.net/mobile/help.html");
    }
        
    public void setURL(String url) {   	
		ConnectivityManager connMgr = (ConnectivityManager)(getSystemService(Context.CONNECTIVITY_SERVICE));
    	android.net.NetworkInfo wifi = connMgr.getNetworkInfo(ConnectivityManager.TYPE_WIFI);
    	android.net.NetworkInfo mobile = connMgr.getNetworkInfo(ConnectivityManager.TYPE_MOBILE);
    	
    	boolean have_network = false;
    	if (wifi != null) {
    		have_network = wifi.isConnected();
    	} 
    	if (!have_network && mobile != null) {
    		have_network = mobile.isConnected();
    	}
    	if (!have_network) {
    		return;
    	}

    	if (webview == null) {
    		webview = new WebView(this);
    		webview.getSettings().setJavaScriptEnabled(true);
    	}

    	if (!url.equals(current_url)) {
    		current_url = url;    		
    		webview.loadUrl(current_url);
    	}    	
    	setContentView(webview);
    }
}
