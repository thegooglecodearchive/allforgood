package nl.jteam.search.solrext.spatial.lucene;

import org.apache.lucene.index.Term;
import org.apache.lucene.search.Query;
import org.apache.lucene.search.TermQuery;
import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;

/**
 * Tests for {@link nl.jteam.search.solrext.spatial.lucene.SpatialFilter}
 */
public class SpatialFilterTest {

    /**
     * Pass condition: Two SpatialFilters with different queries but the same search coordinates, do not have the same
     *                 hashCode.  However two SpatialFilters that do, share the same hashCode
     */
    @Test
    public void testHashCode_differentQueries() {
        Query query1 = new TermQuery(new Term("field", "value1"));
        SpatialFilter filter1 = new SpatialFilter(40.3, 50.9, 10, "_tier_", query1);

        Query query2 = new TermQuery(new Term("field", "value2"));
        SpatialFilter filter2 = new SpatialFilter(40.3, 50.9, 10, "_tier_", query2);

        Query query3 = new TermQuery(new Term("field", "value1"));
        SpatialFilter filter3 = new SpatialFilter(40.3, 50.9, 10, "_tier_", query3);

        assertFalse("SpatialFilters with different queries have same hashCode", filter1.hashCode() == filter2.hashCode());
        assertEquals(filter1.hashCode(), filter3.hashCode());
    }

    /**
     * Pass condition: Two SpatialFilters with the same queries but different search coordinates, do not have the same
     *                 hashCode.  However two SpatialFilters that do, share the same hashCode
     */
    @Test
    public void testHashCode_sameQueriesDifferentCoordinates() {
        Query query1 = new TermQuery(new Term("field", "value1"));
        SpatialFilter filter1 = new SpatialFilter(9.2, 8.4, 50, "_tier_", query1);

        Query query2 = new TermQuery(new Term("field", "value1"));
        SpatialFilter filter2 = new SpatialFilter(40.3, 50.9, 10, "_tier_", query2);

        Query query3 = new TermQuery(new Term("field", "value1"));
        SpatialFilter filter3 = new SpatialFilter(9.2, 8.4, 50, "_tier_", query3);

        assertFalse("SpatialFilters with different coordinates have same hashCode", filter1.hashCode() == filter2.hashCode());
        assertEquals(filter1.hashCode(), filter3.hashCode());
    }

    /**
     * Pass condition: Two SpatialFilters with different queries but the same search coordinates, are not equal.
     *                 However two SpatialFilters that do, are equal
     */
    @Test
    public void testEquals_differentQueries() {
        Query query1 = new TermQuery(new Term("field", "value1"));
        SpatialFilter filter1 = new SpatialFilter(40.3, 50.9, 10, "_tier_", query1);

        Query query2 = new TermQuery(new Term("field", "value2"));
        SpatialFilter filter2 = new SpatialFilter(40.3, 50.9, 10, "_tier_", query2);

        Query query3 = new TermQuery(new Term("field", "value1"));
        SpatialFilter filter3 = new SpatialFilter(40.3, 50.9, 10, "_tier_", query3);

        assertFalse("SpatialFilters with different queries should not be equal", filter1.equals(filter2));
        assertEquals(filter1, filter3);
    }

    /**
     * Pass condition: Two SpatialFilters with the same queries but different search coordinates, are not equal.
     *                 However two SpatialFilters that do, are equal
     */
    @Test
    public void testEquals_differentCoordinates() {
        Query query1 = new TermQuery(new Term("field", "value1"));
        SpatialFilter filter1 = new SpatialFilter(9.2, 8.4, 50, "_tier_", query1);

        Query query2 = new TermQuery(new Term("field", "value1"));
        SpatialFilter filter2 = new SpatialFilter(40.3, 50.9, 10, "_tier_", query2);

        Query query3 = new TermQuery(new Term("field", "value1"));
        SpatialFilter filter3 = new SpatialFilter(9.2, 8.4, 50, "_tier_", query3);

        assertFalse("SpatialFilters with different coordinates should not be equal", filter1.equals(filter2));
        assertEquals(filter1, filter3);
    }
}
