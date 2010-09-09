package nl.jteam.search.solrext.spatial.lucene;

import org.apache.lucene.search.FieldComparatorSource;
import org.apache.lucene.search.FieldComparator;
import org.apache.lucene.index.IndexReader;

import java.io.IOException;

import nl.jteam.search.solrext.spatial.lucene.distance.DistanceFilter;

/**
 * DistanceFieldComparatorSource is reponsible for creating fieldcomparators for sorting on distance.
 */
public class DistanceFieldComparatorSource extends FieldComparatorSource {

	private DistanceFilter distanceFilter;
	private DistanceComparator comparator;

    /**
     * Constructs a DistanceFieldComparatorSource with the specified distanceFilter.
     * The distanceFilter is used as a source for all the document distances from a central point.
     *
     * @param distanceFilter The specified distanceFiter. Cannot be {@code null}
     */
	public DistanceFieldComparatorSource(DistanceFilter distanceFilter) {
        if (distanceFilter == null) {
            throw new IllegalArgumentException("Argument distanceFilter cannot be null");
        }
		this.distanceFilter = distanceFilter;
	}

    /**
     * Cleans up any resource associated with this field compararor source.
     */
	public void cleanUp() {
		distanceFilter = null;

		if (comparator != null) {
			comparator.cleanUp();
		    comparator = null;
        }
	}

    /**
     * {@inheritDoc}
     */
	public FieldComparator newComparator(String fieldname, int numHits, int sortPos, boolean reversed) throws IOException {
		comparator = new DistanceComparator(distanceFilter, numHits);
		return comparator;
	}


    // ============================================ Inner Classes ======================================================

    /**
     * FieldComparator that uses the calculated distances to sort documents
     */
	private final class DistanceComparator extends FieldComparator {

		private DistanceFilter distanceFilter;
		private double[] values;
		private double bottom;
		private int offset = 0;

        /**
         * Creates a new DistanceComparator which will use the distances calculated by the given DistanceFilter
         *
         * @param distanceFilter DistanceFilter that holds the calculated distances for the documents
         * @param numHits Number of hits that will be sorted by the comparator
         */
		public DistanceComparator(DistanceFilter distanceFilter, int numHits) {
			this.distanceFilter = distanceFilter;
			this.values = new double[numHits];
		}

        /**
         * {@inheritDoc}
         */
		public int compare(int slot1, int slot2) {
			double a = values[slot1];
			double b = values[slot2];
			if (a > b) {
				return 1;
            } else if (a < b) {
				return -1;
            }

			return 0;
		}

        /**
         * Cleans up the FieldComparator by releasing the reference to the DistanceFilter
         */
		public void cleanUp() {
			distanceFilter = null;
            values = null;
		}

        /**
         * {@inheritDoc}
         */
		public int compareBottom(int doc) {
			double v2 = distanceFilter.getDistance(doc + offset);

			if (bottom > v2) {
				return 1;
			} else if (bottom < v2) {
				return -1;
			}
			return 0;
		}

        /**
         * {@inheritDoc}
         */
		public void copy(int slot, int doc) {
			values[slot] = distanceFilter.getDistance(doc + offset);
		}

        /**
         * {@inheritDoc}
         */
		public void setBottom(int slot) {
			this.bottom = values[slot];
		}

        /**
         * {@inheritDoc}
         */
		public void setNextReader(IndexReader reader, int docBase) throws IOException {
			// each reader in a segmented base has an offset based on the maxDocs of previous readers
			offset = docBase;
		}

        /**
         * {@inheritDoc}
         */
		public Comparable<Double> value(int slot) {
			return values[slot];
		}
	}

}
