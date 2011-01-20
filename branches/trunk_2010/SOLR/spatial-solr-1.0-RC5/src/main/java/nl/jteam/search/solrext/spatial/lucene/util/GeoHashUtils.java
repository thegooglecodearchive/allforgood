package nl.jteam.search.solrext.spatial.lucene.util;

import java.util.HashMap;
import java.util.Map;

/**
 * Utilities for encoding and decoding geohashes. Based on http://en.wikipedia.org/wiki/Geohash.
 */
public class GeoHashUtils {

	private static char[] BASE_32 = {'0','1','2','3','4','5','6','7','8','9', 'b','c','d','e','f','g','h','j','k','m',
							         'n','p','q','r','s','t','u','v','w','x', 'y','z'} ;

	private final static Map<Character, Integer> DECODE_MAP = new HashMap<Character, Integer>();

    private static int PRECISION = 12;
    private static int[] BITS = {16, 8, 4, 2, 1};

    static {
        for (int i = 0; i < BASE_32.length; i++ ){
            DECODE_MAP.put(BASE_32[i], i);
        }
    }

    private GeoHashUtils() {
    }

    /**
     * Encodes the given latitude and longitude into a geohash
     *
     * @param latitude Latitude to encode
     * @param longitude Longitude to encode
     * @return Geohash encoding of the longitude and latitude
     */
	public static String encode(double latitude, double longitude) {
		double[] latInterval = {-90.0,  90.0};
		double[] lngInterval = {-180.0, 180.0};

		StringBuilder geohash = new StringBuilder();
		boolean isEven = true;

		int bit = 0;
        int ch = 0;

		while (geohash.length() < PRECISION) {
			double mid = 0.0;
			if (isEven) {
				mid = (lngInterval[0] + lngInterval[1]) / 2D;
				if (longitude > mid){
					ch |= BITS[bit];
					lngInterval[0] = mid;
				} else {
					lngInterval[1] = mid;
				}

			} else {
				mid = (latInterval[0] + latInterval[1]) / 2D;
				if(latitude > mid){
					ch |= BITS[bit];
					latInterval[0] = mid;
				} else {
					latInterval[1] = mid;
				}
			}

			isEven = !isEven;

			if (bit < 4){
				bit++;
			} else {
				geohash.append(BASE_32[ch]);
				bit = 0;
				ch = 0;
			}
		}

		return geohash.toString();
	}

    /**
     * Decodes the given geohash into a latitude and longitude
     *
     * @param geohash Geohash to deocde
     * @return Array with the latitude at index 0, and longitude at index 1
     */
	public static double[] decode(String geohash) {
		double[] latInterval = {-90.0, 90.0};
		double[] lngInterval = {-180.0, 180.0};

		boolean isEven = true;

		double latitude;
        double longitude;
		for (int i = 0; i < geohash.length(); i++) {
			int cd = DECODE_MAP.get(geohash.charAt(i));

            for (int mask : BITS) {
                if (isEven) {
                    if ((cd & mask) != 0) {
                        lngInterval[0] = (lngInterval[0] + lngInterval[1]) / 2D;
                    } else {
                        lngInterval[1] = (lngInterval[0] + lngInterval[1]) / 2D;
                    }

                } else {
                    if ((cd & mask) != 0) {
                        latInterval[0] = (latInterval[0] + latInterval[1]) / 2D;
                    } else {
                        latInterval[1] = (latInterval[0] + latInterval[1]) / 2D;
                    }
                }
                isEven = !isEven;
            }

		}
		latitude  = (latInterval[0] + latInterval[1]) / 2;
		longitude = (lngInterval[0] + lngInterval[1]) / 2;

		return new double[] {latitude, longitude};
	}
}
