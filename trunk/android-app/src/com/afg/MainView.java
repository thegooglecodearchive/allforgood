package com.afg;

import android.app.TabActivity;
import android.content.Intent;
import android.content.res.Resources;
import android.os.Bundle;
import android.widget.TabHost;

public class MainView extends TabActivity {
	TabHost tabHost;

   /** Called when the activity is first created. */
    @Override   
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
    	setContentView(R.layout.main);
    	
    	
    	tabHost = getTabHost();
    	Resources res = getResources();
    	    	
        TabHost.TabSpec spec;  // Resusable TabSpec for each tab
        Intent intent;  // Reusable Intent for each tab

        // Initialize a TabSpec for each tab and add it to the TabHost
        intent = new Intent().setClass(this, TabContent.class);
        spec = tabHost.newTabSpec("content").setIndicator(""
        		,res.getDrawable(R.drawable.ic_tab_search)
        		).setContent(intent);
        tabHost.addTab(spec);

        intent = new Intent().setClass(this, TabSettings.class);
        spec = tabHost.newTabSpec("settings").setIndicator(""
        		,res.getDrawable(R.drawable.ic_tab_preferences)
        		).setContent(intent);
        tabHost.addTab(spec);

        intent = new Intent().setClass(this, TabHelp.class);
        spec = tabHost.newTabSpec("help").setIndicator(""
        		,res.getDrawable(R.drawable.ic_tab_help)
        		).setContent(intent);
        tabHost.addTab(spec);

        tabHost.setCurrentTab(0);
    }
}