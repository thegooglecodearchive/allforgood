package com.afg;

import com.afg.R;

import android.app.Activity;
import android.content.SharedPreferences;
import android.content.res.Resources;
import android.graphics.Color;
import android.os.Bundle;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

public class TabSettings extends Activity {
	
	private EditText location_input;
	
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout wrapper = new LinearLayout(this);

        wrapper.setOrientation(LinearLayout.VERTICAL); 
		wrapper.setBackgroundColor(Color.WHITE);
        // left, top, right, bottom
		wrapper.setPadding(6, 6, 6, 0);

        TextView label = new TextView(this);
        label.setText("Enter desired location");
        label.setTextColor(Color.rgb(64,64,64));
        label.setTextSize(24);
        label.setPadding(3, 0, 3, 6);
        wrapper.addView(label);

        location_input = new EditText(this); 
        location_input.setPadding(6, 0, 3, 0);
        location_input.setSingleLine();
        location_input.setHint("Using Current Location");
        location_input.setHintTextColor(Color.rgb(64, 64, 255)); 
        Resources res = getResources();
    	SharedPreferences settings = getSharedPreferences(res.getString(R.string.prefs_file_name), 0);
        String where = settings.getString(res.getString(R.string.location_pref_key), "");
        location_input.setText(where);
        wrapper.addView(location_input);
        
		TextView note = new TextView(this);
        note.setText("leave blank for current location");
        note.setTextColor(Color.rgb(64,64,64));
        note.setTextSize(20);
        note.setPadding(3, 6, 3, 0);
        wrapper.addView(note);
		setContentView(wrapper);
    }

    private void saveLocationPref() {
	    Resources res = getResources();
	    SharedPreferences settings = getSharedPreferences(res.getString(R.string.prefs_file_name), 0);
	    SharedPreferences.Editor editor = settings.edit();
	    editor.putString(res.getString(R.string.location_pref_key), location_input.getText().toString());
	    editor.commit();
    }
    
    @Override
    protected void onPause(){
    	super.onPause();
    	this.saveLocationPref();
    }

    @Override
    protected void onStop(){
    	super.onStop();
    	this.saveLocationPref();
    }
}