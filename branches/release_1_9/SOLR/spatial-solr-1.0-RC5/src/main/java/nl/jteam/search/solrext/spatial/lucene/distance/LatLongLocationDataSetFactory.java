package nl.jteam.search.solrext.spatial.lucene.distance;

import nl.jteam.search.solrext.spatial.lucene.geometry.Point;
import org.apache.lucene.index.IndexReader;
import org.apache.lucene.search.FieldCache;

import java.io.IOException;

/**
 * Implementation of {@link LocationDataSetFactory} that builds LocationDataSet based on 2 fields representing latitude
 * and longitude.
 */
public class LatLongLocationDataSetFactory implements LocationDataSetFactory {

    private final String latField;
    private final String lngField;

    /**
     * Creates a new LatLongLocationDataSetFactory that will use the latitude and longitude data read from the fields
     * with the given names
     *
     * @param latField Name of the latitude field
     * @param lngField Name of the longitude field
     */
    public LatLongLocationDataSetFactory(String latField, String lngField) {
        this.latField = latField;
        this.lngField = lngField;
    }

    /**
     * {@inheritDoc}
     */
    public LocationDataSet buildLocationDataSet(IndexReader indexReader) throws IOException {
        return new LatLongLocationDataSet(
                FieldCache.DEFAULT.getDoubles(indexReader, latField, FieldCache.NUMERIC_UTILS_DOUBLE_PARSER),
                FieldCache.DEFAULT.getDoubles(indexReader, lngField, FieldCache.NUMERIC_UTILS_DOUBLE_PARSER));
    }

    // ================================================= Inner Classes =================================================

    /**
     * Implementation of LocationDataSet that uses fields that represent latitude and longitude to construct the Point
     * for a document.
     */
    private class LatLongLocationDataSet implements LocationDataSet {

        private double[] latIndex;
        private double[] lngIndex;

        /**
         * Creates a new LatLongLocationDataSet which uses the values in the given latitude and longitude indexes to create
         * Points for documents
         *
         * @param latIndex Array containing the latitude field values taken from the index
         * @param lngIndex Array containing the longitude field values taken from the index
         */
        private LatLongLocationDataSet(double[] latIndex, double[] lngIndex) {
            this.latIndex = latIndex;
            this.lngIndex = lngIndex;
        }

        /**
         * {@inheritDoc}
         */
        public Point getPoint(int docId) {
            return new Point(latIndex[docId], lngIndex[docId]);
        }
    }
}
