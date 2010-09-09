package nl.jteam.search.solrext.spatial.lucene.distance;

import org.apache.lucene.index.IndexReader;

import java.util.logging.Logger;
import java.util.logging.Level;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Callable;
import java.util.concurrent.Future;
import java.util.concurrent.ExecutionException;
import java.io.IOException;

import nl.jteam.search.solrext.spatial.lucene.geometry.Point;
import nl.jteam.search.solrext.spatial.lucene.geometry.GeoDistanceCalculator;
import nl.jteam.search.solrext.spatial.lucene.util.DistanceUnit;

/**
 * Implementation of {@link DistanceFilter} that uses multiple threads to iterate in
 * parallel, over the BitSet to be filtered.
 * <p/>
 * To manage the threads, an ExecutorService is used, which allows users of this class to have fine grained control over
 * how many threads should be created, and what to do when there isn't any threads left in the pool.
 */
public class ThreadedDistanceFilter implements DistanceFilter {

    private final Logger log = Logger.getLogger(getClass().getName());

    private final List<Map<Integer, Double>> distanceMaps = new ArrayList<Map<Integer, Double>>();
    private final double lat;
    private final double lng;
    private final double radius;
    private final DistanceUnit unit;

    private final GeoDistanceCalculator distanceCalculator;
    private final LocationDataSetFactory dataSetFactory;

    private final ExecutorService executorService;
    private final int threadCount;

    private int nextOffset = 0;

    /**
     * Creates a new ThreadedDistanceFilter that will filter out documents that are outside of the given radius of the
     * central point defined by the given latitude and longitude
     *
     * @param lat                Latitude of the central point
     * @param lng                Longitude of the central point
     * @param radius             Radius that documents must be within from the central point to pass the filter
     * @param unit               Unit of distance the radius is in
     * @param dataSetFactory     LocationDataSetFactory which can be used to create LocationDataSets from an IndexReader
     * @param distanceCalculator GeoDistanceCalculator that will be used to calculate the distances between points
     * @param executorService    ExecutorService which will manage the execution of the threads
     * @param threadCount        Number of threads that the filter should try to split its work across
     */
    public ThreadedDistanceFilter(
            double lat,
            double lng,
            double radius,
            DistanceUnit unit,
            LocationDataSetFactory dataSetFactory,
            GeoDistanceCalculator distanceCalculator,
            ExecutorService executorService,
            int threadCount) {

        this.lat = lat;
        this.lng = lng;
        this.radius = radius;
        this.unit = unit;
        this.distanceCalculator = distanceCalculator;
        this.dataSetFactory = dataSetFactory;
        this.executorService = executorService;
        this.threadCount = threadCount;
    }

    /**
     * {@inheritDoc}
     */
    public Map<Integer, Double> getDistances() {
        Map<Integer, Double> combinedDistances = new HashMap<Integer, Double>();
        for (Map<Integer, Double> distanceMap : distanceMaps) {
            combinedDistances.putAll(distanceMap);
        }
        return combinedDistances;
    }

    /**
     * {@inheritDoc}
     */
    public Double getDistance(int docId) {
        for (Map<Integer, Double> distanceMap : distanceMaps) {
            Double distance = distanceMap.get(docId);
            if (distance != null) {
                return distance;
            }
        }
        return null;
    }

    /**
     * {@inheritDoc}
     */
    public BitSet bits(final IndexReader reader, final BitSet bits) throws IOException {
        final LocationDataSet dataSet = dataSetFactory.buildLocationDataSet(reader);

        int maxLength = bits.length();
        int threadSize = maxLength / threadCount;
        List<Callable<IterationResult>> tasks = new ArrayList<Callable<IterationResult>>();

        long startTime = System.currentTimeMillis();
        for (int i = 0; i < threadCount; i++) {
            final int start = i * threadSize;
            // if the last batch of documents has been reached, then maxLength should be end
            final int end = (i == threadCount - 1) ? maxLength : Math.min((i + 1) * threadSize, maxLength);
            tasks.add(new Callable<IterationResult>() {
                public IterationResult call() throws Exception {
                    return iterate(dataSet, bits, start, end, end - start, reader);
                }
            });
            if (log.isLoggable(Level.FINE)) {
                log.fine(String.format("Created thread starting at %d and ending at %d", start, end));
            }
        }

        BitSet result = new BitSet(bits.cardinality());

        try {
            List<Future<IterationResult>> results = executorService.invokeAll(tasks);
            for (Future<IterationResult> resultFuture : results) {
                IterationResult iterationResult = resultFuture.get();
                result.or(iterationResult.getBitSet());
                distanceMaps.add(iterationResult.getDistanceById());
            }
        } catch (InterruptedException ie) {
            throw new RuntimeException("InterruptedException thrown while executing tasks", ie);
        } catch (ExecutionException ee) {
            throw new RuntimeException("ExecutionException thrown while retrieving results of tasks", ee);
        }

        nextOffset += reader.maxDoc();

        if (log.isLoggable(Level.FINE)) {
            long endTime = System.currentTimeMillis();
            log.fine(String.format("Filter took %dms to complete", endTime - startTime));
        }

        return result;
    }

    // ================================================ Helper Methods =================================================

    /**
     * Iterates over the set bits in the given BitSet from the given start to end range, calculating the distance of the
     * documents and determining which are within the distance radius of the central point.
     *
     * @param dataSet        LocationDataSet containing the document locations that can be used to calculate the distance each
     *                       document is from the central point
     * @param originalBitSet BitSet which has bits set identifying which documents should be checked to see if their
     *                       distance falls within the radius
     * @param start          Index in the BitSet that the method will start at
     * @param end            Index in the BitSet that the method will stop at
     * @param size           Size the the resulting BitSet should be created at (most likely end - start)
     * @param reader         IndexReader for checking if the document has been deleted
     * @return IterationResult containing all the results of the method.
     */
    protected IterationResult iterate(LocationDataSet dataSet, BitSet originalBitSet, int start, int end, int size, IndexReader reader) {
        BitSet bitSet = new BitSet(size);

        Map<Integer, Double> distanceById = new HashMap<Integer, Double>();

        long startTime = System.currentTimeMillis();
        int docId = originalBitSet.nextSetBit(start);
        while (docId != -1 && docId < end) {
            if (reader.isDeleted(docId)) {
                docId = originalBitSet.nextSetBit(docId + 1);
                continue;
            }

            Point point = dataSet.getPoint(docId);
            double distance = distanceCalculator.calculate(lat, lng, point.getX(), point.getY(), unit);
            if (distance < radius) {
                bitSet.set(docId);
                distanceById.put(docId + nextOffset, distance);
            }

            docId = originalBitSet.nextSetBit(docId + 1);
        }
        long endTime = System.currentTimeMillis();
        if (log.isLoggable(Level.FINE)) {
            log.fine(String.format("Thread took %dms to complete", endTime - startTime));
        }
        return new IterationResult(bitSet, distanceById);
    }

    // ================================================= Inner Classes =================================================

    /**
     * Wrapper of the results from {@link ThreadedDistanceFilter#iterate(LocationDataSet, BitSet, int, int, int, IndexReader)}.
     * This allows the method to operate in almost total isolation in separate threads.
     */
    protected class IterationResult {

        private BitSet bitSet;
        private Map<Integer, Double> distanceById;

        /**
         * Creates a new IterationResult that wraps the given BitSet
         *
         * @param bitSet       BitSet to wrap
         * @param distanceById Document IDs with their calculated distances
         */
        public IterationResult(BitSet bitSet, Map<Integer, Double> distanceById) {
            this.bitSet = bitSet;
            this.distanceById = distanceById;
        }

        /**
         * Returns the wrapped BitSet
         *
         * @return Wrapped BitSet
         */
        public BitSet getBitSet() {
            return bitSet;
        }

        /**
         * Returns the document IDs and calculated distances contained in this result
         *
         * @return Document IDs and calculated distances contained in this result
         */
        public Map<Integer, Double> getDistanceById() {
            return distanceById;
        }
    }
}
