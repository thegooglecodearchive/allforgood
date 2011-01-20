package com.afg;

import android.location.Location;
import android.location.LocationManager;
import android.location.LocationListener;

import android.net.ConnectivityManager;
import android.os.Bundle;
import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.res.Resources;
import android.webkit.WebView;
import android.widget.TextView;

import java.net.URLEncoder;

import com.afg.R;

public class TabContent extends Activity {
	Resources res;

	boolean development = true;

	private String current_url = "";    
    private String lat = "";
    private String lng = "";

	private WebView webview = null;

    private String getLocationParameter() {
    	String rtn = "";
    	SharedPreferences settings = getSharedPreferences(res.getString(R.string.prefs_file_name), 0);
        String where = settings.getString(res.getString(R.string.location_pref_key), rtn);
        if (where.length() > 0 || lat.length() < 1 || lng.length() < 1) {
			rtn = "&up_where=" + URLEncoder.encode(where);
        } else {
        	rtn = "&up_lat=" + lat + "&up_lng=" + lng; 
        }

    	return rtn;
    }
    
    private String getCacheParameter() {
        String rtn = (development ? "&nocache=1" : "");
        return rtn;
    }
    
    private String getGadgetURLParameter() {
        String rtn = (development ? res.getString(R.string.google_gadget_development_url) : 
        	                        res.getString(R.string.google_gadget_url));
        return "&url=" + rtn;
    }
    
    private void initLocation() {
    	// Define a listener that responds to location updates
    	LocationListener locationListener = new LocationListener() {
    		public void onLocationChanged(Location location) {
    			// Called when a new location is found by the network location provider.    			
    			if (location != null) {
    				lat = Double.toString(location.getLatitude());
    				lng = Double.toString(location.getLongitude());
    			}
    			setWebViewURL();
    		}
    		public void onStatusChanged(String provider, int status, Bundle extras) {}
    		public void onProviderEnabled(String provider) {}
    		public void onProviderDisabled(String provider) {}
    	};
    	
    	// Acquire a reference to the system Location Manager
    	LocationManager locationManager = (LocationManager)this.getSystemService(Context.LOCATION_SERVICE);

    	// Register the listener with the Location Manager to receive location updates
    	locationManager.requestLocationUpdates(LocationManager.NETWORK_PROVIDER, 3600 * 1000, 5 * 1000, locationListener);
    }

    
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        res = getResources();
        initLocation();
    }

    public void onResume() {
        super.onResume();
        setWebViewURL();
    }
    
    public void setWebViewURL() {   	
        TextView textview = new TextView(this);
        textview.setText("Lat = " + lat);
        setContentView(textview);
 
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
            textview = new TextView(this);
            textview.setText(res.getString(R.string.msg_no_network));
            setContentView(textview);
    		return;
    	}

    	if (webview == null) {
    		webview = new WebView(this);
    		webview.getSettings().setJavaScriptEnabled(true);
    	}
    	
    	String url = res.getString(R.string.google_gadget_loader) + 
    	             getCacheParameter() + getGadgetURLParameter() + 
    	             getLocationParameter();

    	if (!url.equals(current_url)) {
    		current_url = url;
    		webview.loadUrl(current_url);    		
    	}    	
    	setContentView(webview);
    }    
}