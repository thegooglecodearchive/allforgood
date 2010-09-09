package nl.jteam.search.solrext.spatial.lucene.distance;

import nl.jteam.search.solrext.spatial.lucene.geometry.ArcDistanceCalculator;
import nl.jteam.search.solrext.spatial.lucene.geometry.Point;
import nl.jteam.search.solrext.spatial.lucene.geometry.GeoDistanceCalculator;
import nl.jteam.search.solrext.spatial.lucene.util.DistanceUnit;
import nl.jteam.search.solrext.spatial.lucene.distance.LocationDataSet;
import nl.jteam.search.solrext.spatial.lucene.distance.LocationDataSetFactory;
import nl.jteam.search.solrext.spatial.lucene.distance.ThreadedDistanceFilter;
import org.apache.lucene.index.IndexReader;
import org.apache.lucene.index.ParallelReader;
import org.junit.Test;
import static org.junit.Assert.*;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;

/**
 * Tests for {@link ThreadedDistanceFilterTest}
 */
public class ThreadedDistanceFilterTest {

    private final LocationDataSet locationDataSet = new LocationDataSet() {

        private List<Point> points = Arrays.asList(new Point(4.53, 30.61), new Point(4.51, 31.01), new Point(5.69, 40.89));

        public Point getPoint(int docId) {
            return points.get(docId);
        }
    };


    @Test
    public void testGeoCalculation_correctArgumentPassing() throws Exception {
        double sourceLatitude = 1.0;
        double sourceLongitude = 2.0;
        final double targetLatitude = 3.0;
        final double targetLongitude = 4.0;

        LocationDataSetFactory dataSetFactory = new LocationDataSetFactory() {

            public LocationDataSet buildLocationDataSet(IndexReader indexReader) throws IOException {
                return new LocationDataSet() {

                    private List<Point> points = Arrays.asList(new Point(targetLatitude, targetLongitude));

                    public Point getPoint(int docId) {
                        return points.get(docId);
                    }
                };
            }
        };

        StubGeoDistanceCalculator distanceCalculator = new StubGeoDistanceCalculator();
        ExecutorService executorService = Executors.newFixedThreadPool(1);

        ThreadedDistanceFilter filter =
                new ThreadedDistanceFilter(sourceLatitude, sourceLongitude, 10, DistanceUnit.KILOMETERS, dataSetFactory, distanceCalculator, executorService, 1);

        IndexReader indexReader = new ParallelReader() {
            @Override
            public int maxDoc() {
                return 0;
            }
        };
        BitSet bitSet = new BitSet(1);
        bitSet.set(0);
        filter.bits(indexReader, bitSet);

        assertEquals(sourceLatitude, distanceCalculator.getSourceLatitude(), 0);
        assertEquals(sourceLongitude, distanceCalculator.getSourceLongitude(), 0);
        assertEquals(targetLatitude, distanceCalculator.getTargetLatitude(), 0);
        assertEquals(targetLongitude, distanceCalculator.getTargetLongitude(), 0);
    }

    /**
     * Pass condition: 2 threads with the correct start and end indexes are created based on the BitSet given in the method
     * call, and the number of threads that were requested.
     *
     * @throws java.io.IOException Can be thrown by the ParallelReader which is used as the IndexReader for the test
     */
    @Test
    public void testBits() throws IOException {
        LocationDataSetFactory dataSetFactory = new LocationDataSetFactory() {
            public LocationDataSet buildLocationDataSet(IndexReader indexReader) throws IOException {
                return locationDataSet;
            }
        };

        ExecutorService executorService = new ThreadPoolExecutor(2, 6, 8, TimeUnit.SECONDS, new LinkedBlockingDeque<Runnable>());

        BitSet bitSet = new BitSet(13);
        bitSet.set(2, 6);
        bitSet.set(8, 9);
        bitSet.set(11);

        final List<IterateCallInfo> infoList = Collections.synchronizedList(new ArrayList<IterateCallInfo>());
        ThreadedDistanceFilter distanceFilter = new ThreadedDistanceFilter(4.52, 30.81, 30, DistanceUnit.MILES, dataSetFactory, new ArcDistanceCalculator(), executorService, 2) {

            @Override
            protected IterationResult iterate(LocationDataSet dataSet, BitSet originalBitSet, int start, int end, int size, IndexReader reader) {
                infoList.add(new IterateCallInfo(start, end, size));
                return new IterationResult(new BitSet(), Collections.EMPTY_MAP);
            }
        };

        IndexReader indexReader = new ParallelReader() {
            @Override
            public int maxDoc() {
                return 0;
            }
        };

        distanceFilter.bits(indexReader, bitSet);

        assertEquals(2, infoList.size());

        Collections.sort(infoList, new Comparator<IterateCallInfo>() {
            public int compare(IterateCallInfo info1, IterateCallInfo info2) {
                return info1.getStart() - info2.getStart();
            }
        });

        IterateCallInfo callInfo = infoList.get(0);
        assertEquals(0, callInfo.getStart());
        assertEquals(6, callInfo.getEnd());
        assertEquals(6, callInfo.getSize());

        callInfo = infoList.get(1);
        assertEquals(6, callInfo.getStart());
        assertEquals(12, callInfo.getEnd());
        assertEquals(6, callInfo.getSize());
    }

    /**
     * Pass condition: Of the 3 documents with points, 1 is outside of the radius and should be filtered out, 1 has been
     * deleted so it should also be filtered out, leaving just 1 that passes the filter.  Its distance
     * should be recorded in the calculated distances of the filter
     *
     * @throws IOException Can be thrown by the ParallelReader which is used as the IndexReader for the test
     */
    public void testIterate() throws IOException {
        IndexReader indexReader = new ParallelReader() {
            @Override
            public boolean isDeleted(int n) {
                return n == 1;
            }
        };

        BitSet bitSet = new BitSet(2);
        bitSet.set(0);
        bitSet.set(1);
        bitSet.set(2);

        ThreadedDistanceFilter distanceFilter = new ThreadedDistanceFilter(4.52, 30.81, 30, DistanceUnit.MILES, null, new ArcDistanceCalculator(), null, 0);

        ThreadedDistanceFilter.IterationResult result = distanceFilter.iterate(locationDataSet, bitSet, 0, 3, 3, indexReader);

        assertNotNull(result);

        BitSet resultingBitSet = result.getBitSet();
        assertNotNull(resultingBitSet);
        assertTrue(resultingBitSet.get(0));
        assertFalse(resultingBitSet.get(1));
        assertFalse(resultingBitSet.get(2));

        assertNotNull(result.getDistanceById());
        assertEquals(1, result.getDistanceById().size());
    }

    // ================================================= Inner Classes =================================================

    private static class IterateCallInfo {

        private final int start;
        private final int end;
        private final int size;

        private IterateCallInfo(int start, int end, int size) {
            this.start = start;
            this.end = end;
            this.size = size;
        }

        public int getStart() {
            return start;
        }

        public int getEnd() {
            return end;
        }

        public int getSize() {
            return size;
        }
    }

    /**
     * Dummy implementation. Used for unit test to assure that the given arguments to a distance calculator are given correctly .
     */
    class StubGeoDistanceCalculator implements GeoDistanceCalculator {

        private double sourceLatitude;
        private double sourceLongitude;
        private double targetLatitude;
        private double targetLongitude;

        public double calculate(double sourceLatitude, double sourceLongitude, double targetLatitude, double targetLongitude, DistanceUnit unit) {
            this.sourceLatitude = sourceLatitude;
            this.sourceLongitude = sourceLongitude;
            this.targetLatitude = targetLatitude;
            this.targetLongitude = targetLongitude;
            return 0.0;
        }

        public double getSourceLatitude() {
            return sourceLatitude;
        }

        public double getSourceLongitude() {
            return sourceLongitude;
        }

        public double getTargetLatitude() {
            return targetLatitude;
        }

        public double getTargetLongitude() {
            return targetLongitude;
        }
    }
}
