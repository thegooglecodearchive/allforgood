package nl.jteam.search.solrext.spatial.lucene.distance;

import org.apache.lucene.index.IndexReader;
import org.apache.lucene.search.FieldCache;

import java.io.IOException;

import nl.jteam.search.solrext.spatial.lucene.geometry.Point;
import nl.jteam.search.solrext.spatial.lucene.util.GeoHashUtils;

/**
 * Implementation of {@link LocationDataSetFactory} that supports location information
 * being contained in a single geohashed field.
 *
 * @see nl.jteam.search.solrext.spatial.lucene.util.GeoHashUtils }
 */
public class GeoHashLocationDataSetFactory implements LocationDataSetFactory {

    private final String geoHashField;

    /**
     * Creates a new GeoHashLocationDataSetFactory that will read from the field with the given name
     *
     * @param geoHashField Name of the field containing the geohashes
     */
    public GeoHashLocationDataSetFactory(String geoHashField) {
        this.geoHashField = geoHashField;
    }

    /**
     * {@inheritDoc}
     */
    public LocationDataSet buildLocationDataSet(IndexReader indexReader) throws IOException {
        return new GeoHashLocationDataSet(FieldCache.DEFAULT.getStringIndex(indexReader, geoHashField));
    }

    // ================================================= Inner Classes =================================================

    /**
     * Implementation of LocationDataSet which uses a geohash stored in a single index field
     */
    private class GeoHashLocationDataSet implements LocationDataSet {

        private FieldCache.StringIndex index;

        /**
         * Creates a new GeoHashLocationDataSet which uses the values in the given index
         *
         * @param index A StringIndex containing the values of the geohash field taken from the index
         */
        private GeoHashLocationDataSet(FieldCache.StringIndex index) {
            this.index = index;
        }

        /**
         * {@inheritDoc}
         */
        public Point getPoint(int docId) {
            String fieldValue = index.lookup[index.order[docId]];
            double[] coords = GeoHashUtils.decode(fieldValue);
            return new Point(coords[0], coords[1]);
        }
    }
}
