package nl.jteam.search.solrext.spatial.lucene;

import nl.jteam.search.solrext.spatial.lucene.distance.*;
import nl.jteam.search.solrext.spatial.lucene.geometry.GeoDistanceCalculator;
import nl.jteam.search.solrext.spatial.lucene.tier.CartesianShapeFilterBuilder;
import nl.jteam.search.solrext.spatial.lucene.util.DistanceUnit;
import org.apache.lucene.index.IndexReader;
import org.apache.lucene.search.*;
import org.apache.lucene.util.DocIdBitSet;

import java.io.IOException;
import java.util.BitSet;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.LinkedBlockingDeque;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;

/**
 * SpatialFilter is a proper Lucene Filter that filters out documents that are outside of a certain radius of a central
 * point.  At the heart of the filtering process is the {@link nl.jteam.search.solrext.spatial.lucene.tier.CartesianShapeFilter} which
 * uses cartesian tiers to filter out the majority of documents.  The remaining documents are sent through an instance of
 * {@link DistanceFilter} which calculates the actual distance of each document.
 * <p/>
 * For maximum compatability, distances in both miles and kilometers are supported and for maximum performance and for
 * performance it is also possible to disabled the {@link nl.jteam.search.solrext.spatial.lucene.distance.DistanceFilter} step.
 */
public class SpatialFilter extends Filter {

    private DistanceFilter distanceFilter;
    private Filter cartesianFilter;
    private final Query query;

    private final Double latitude;
    private final Double longitude;
    private final Double radius;

    /**
     * Creates a new SpatialFilter which will filter out documents that are outside of the given radius from the central
     * point defined by the given latitude and longitude
     *
     * @param lat Latitude of the central point
     * @param lng Longitude of the central point
     * @param radius Radius from the central point that document must be within in order to pass the filter
     * @param tierFieldPrefix Prefix of the fields that contain the cartesian tier information
     * @param query Query that is going to executed along with the Filter.  This query is executed inside the filter to
     *              reduce the number of documents whose distances need to be calculated
     */
    public SpatialFilter(double lat, double lng, double radius, String tierFieldPrefix, Query query) {
        this.latitude = lat;
        this.longitude = lng;
        this.radius = radius;
        this.query = query;
        
        CartesianShapeFilterBuilder shapeFilterBuilder = new CartesianShapeFilterBuilder(tierFieldPrefix);
        this.cartesianFilter = shapeFilterBuilder.buildFilter(lat, lng, radius);
        this.distanceFilter = new NoOpDistanceFilter();
    }

    /**
     * Creates a new SpatialFilter that uses latitude and longitude information stored in two separate fields
     *
     * @param lat Latitude of the central point
     * @param lng Longitude of the central point
     * @param radius Radius that a document must be within in order to pass the filter
     * @param unit Unit of distance the radius is in
     * @param latField Name of the field with the latitude values
     * @param lngField Name of the field with the longitude values
     * @param tierFieldPrefix Prefix of the fields that contain the cartesian tier information
     * @param distanceCalculator GeoDistanceCalculator that will be used to calculate the distances between points in the
     *                           distance filtering process
     * @param executorService ExecutorService that will be used to manage any threads created as part of the distance
     *                        filtering process
     * @param threadCount Number of threads that the distance filtering process can use to multi-thread its work
     * @param query Query that is going to executed along with the Filter.  This query is executed inside the filter to
     *              reduce the number of documents whose distances need to be calculated
     */
    public SpatialFilter(
            double lat,
            double lng,
            double radius,
            DistanceUnit unit,
            String latField,
            String lngField,
            String tierFieldPrefix,
            GeoDistanceCalculator distanceCalculator,
            ExecutorService executorService,
            int threadCount,
            Query query) {

        this(lat, lng, radius, tierFieldPrefix, query);
        LocationDataSetFactory dataSetFactory = new LatLongLocationDataSetFactory(latField, lngField);
        distanceFilter = new ThreadedDistanceFilter(
                lat,
                lng,
                radius,
                unit,
                dataSetFactory,
                distanceCalculator,
                executorService,
                threadCount);
    }

    /**
     * Creates a new SpatialFilter that uses latitude and longitude information stored in two separate fields.  This method
     * assumes that all calculations are to be executed in the calling thread
     *
     * @param lat Latitude of the central point
     * @param lng Longitude of the central point
     * @param radius Radius that a document must be within in order to pass the filter
     * @param unit Unit of distance the radius is in
     * @param latField Name of the field with the latitude values
     * @param lngField Name of the field with the longitude values
     * @param tierFieldPrefix Prefix of the fields that contain the cartesian tier information
     * @param distanceCalculator GeoDistanceCalculator that will be used to calculate the distances between points in the
     * @param query Query that is going to executed along with the Filter.  This query is executed inside the filter to
     *              reduce the number of documents whose distances need to be calculated
     */
    public SpatialFilter(
            double lat,
            double lng,
            double radius,
            DistanceUnit unit,
            String latField,
            String lngField,
            String tierFieldPrefix,
            GeoDistanceCalculator distanceCalculator,
            Query query) {

        this(   lat,
                lng,
                radius,
                unit,
                latField,
                lngField,
                tierFieldPrefix,
                distanceCalculator,
                new ThreadPoolExecutor(0, 1, 10, TimeUnit.SECONDS, new LinkedBlockingDeque<Runnable>(), new ThreadPoolExecutor.CallerRunsPolicy()),
                1,
                query);
    }

    /**
     * Creates a new SpatialFilter that uses latitude and longitude information stored in a geohash in a single field
     *
     * @param lat Latitude of the central point
     * @param lng Longitude of the central point
     * @param radius Radius that a document must be within in order to pass the filter
     * @param unit Unit of distance the radius is in
     * @param geoHashFieldPrefix Prefix of the field containing the geohas information
     * @param tierFieldPrefix Prefix of the fields that contain the cartesian tier information
     * @param distanceCalculator GeoDistanceCalculator that will be used to calculate the distances between points in the
     *                           distance filtering process
     * @param executorService ExecutorService that will be used to manage any threads created as part of the distance
     *                        filtering process
     * @param threadCount Number of threads that the distance filtering process can use to multi-thread its work
     * @param query Query that is going to executed along with the Filter.  This query is executed inside the filter to
     *              reduce the number of documents whose distances need to be calculated
     */
    public SpatialFilter(
            double lat,
            double lng,
            double radius,
            DistanceUnit unit,
            String geoHashFieldPrefix,
            String tierFieldPrefix,
            GeoDistanceCalculator distanceCalculator,
            ExecutorService executorService,
            int threadCount,
            Query query) {

        this(lat, lng, radius, tierFieldPrefix, query);
        LocationDataSetFactory dataSetFactory = new GeoHashLocationDataSetFactory(geoHashFieldPrefix);
        distanceFilter = new ThreadedDistanceFilter(
                lat,
                lng,
                radius,
                unit,
                dataSetFactory,
                distanceCalculator,
                executorService,
                threadCount);
    }

    /**
     * Creates a new SpatialFilter that uses latitude and longitude information stored in a geohash in a single field.
     * This method assumes that all calculations are to be executed in the calling thread
     *
     * @param lat Latitude of the central point
     * @param lng Longitude of the central point
     * @param radius Radius that a document must be within in order to pass the filter
     * @param unit Unit of distance the radius is in
     * @param geoHashFieldPrefix Prefix of the field containing the geohas information
     * @param tierFieldPrefix Prefix of the fields that contain the cartesian tier information
     * @param distanceCalculator GeoDistanceCalculator that will be used to calculate the distances between points in the
     * @param query Query that is going to executed along with the Filter.  This query is executed inside the filter to
     *              reduce the number of documents whose distances need to be calculated
     */
    public SpatialFilter(
            double lat,
            double lng,
            double radius,
            DistanceUnit unit,
            String geoHashFieldPrefix,
            String tierFieldPrefix,
            GeoDistanceCalculator distanceCalculator,
            Query query) {

        this(   lat,
                lng,
                radius,
                unit,
                geoHashFieldPrefix,
                tierFieldPrefix,
                distanceCalculator,
                new ThreadPoolExecutor(0, 1, 10, TimeUnit.SECONDS, new LinkedBlockingDeque<Runnable>(), new ThreadPoolExecutor.CallerRunsPolicy()),
                1,
                query);
    }

    /**
     * {@inheritDoc}
     */
    @Override
    public DocIdSet getDocIdSet(IndexReader reader) throws IOException {
        FilteredQuery filteredQuery = new FilteredQuery(query, cartesianFilter);
        QueryWrapperFilter filter = new QueryWrapperFilter(filteredQuery);
        
        DocIdSet docIdSet = filter.getDocIdSet(reader);

        BitSet bitSet = new BitSet();
        int docId;
        for (DocIdSetIterator iterator = docIdSet.iterator(); (docId = iterator.nextDoc()) != DocIdSetIterator.NO_MORE_DOCS;) {
            bitSet.set(docId);
        }

        return new DocIdBitSet(distanceFilter.bits(reader, bitSet));
    }

    /**
     * Computes the hashCode of the filter based on the latitude, longitude, radius and query being filtered
     *
     * @return HashCode of the filter
     */
    @Override
    public int hashCode() {
        return latitude.hashCode() ^
               longitude.hashCode() ^
               radius.hashCode() ^
               query.hashCode() ^
               distanceFilter.getDistances().hashCode();
    }

    /**
     * Computers whether the given Object is equal to this filter, based on if its another instance of SpatialFilter and
     * if so, whether the latitudes, longitudes, radii and queries are equal
     *
     * {@inheritDoc}
     */
    @Override
    public boolean equals(Object obj) {
        if (!SpatialFilter.class.isInstance(obj)) {
            return false;
        }
        
        SpatialFilter filter = (SpatialFilter) obj;
        return this.latitude.equals(filter.latitude) &&
               this.longitude.equals(filter.longitude) &&
               this.radius.equals(filter.radius) &&
               this.query.equals(filter.query) &&
               this.distanceFilter.getDistances().equals(filter.getDistanceFilter().getDistances());
    }

    // =============================================== Getters / Setters ===============================================

    /**
     * Returns the instantiated {@link nl.jteam.search.solrext.spatial.lucene.distance.DistanceFilter}.
     *
     * @return Instantiated DistanceFilter.  Will always be non-null.
     */
    public DistanceFilter getDistanceFilter() {
        return distanceFilter;
    }
}
