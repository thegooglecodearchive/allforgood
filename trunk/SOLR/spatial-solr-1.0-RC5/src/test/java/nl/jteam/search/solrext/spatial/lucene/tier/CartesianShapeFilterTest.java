package nl.jteam.search.solrext.spatial.lucene.tier;

import nl.jteam.search.solrext.spatial.lucene.tier.CartesianTierPlotter;
import nl.jteam.search.solrext.spatial.lucene.tier.projection.Projector;
import nl.jteam.search.solrext.spatial.lucene.tier.projection.SinusoidalProjector;
import nl.jteam.search.solrext.spatial.lucene.tier.CartesianShapeFilterBuilder;
import nl.jteam.search.solrext.spatial.lucene.util.GeoHashUtils;
import org.apache.lucene.analysis.WhitespaceAnalyzer;
import org.apache.lucene.document.Document;
import org.apache.lucene.document.Field;
import org.apache.lucene.index.IndexWriter;
import org.apache.lucene.index.Term;
import org.apache.lucene.search.*;
import org.apache.lucene.store.Directory;
import org.apache.lucene.store.RAMDirectory;
import org.apache.lucene.util.NumericUtils;
import org.junit.Test;
import org.junit.BeforeClass;
import static org.junit.Assert.assertEquals;

import java.io.IOException;
import java.util.LinkedList;
import java.util.List;

/**
 * Tests for {@link nl.jteam.search.solrext.spatial.lucene.tier.CartesianShapeFilter}
 */
public class CartesianShapeFilterTest {

    private static Directory directory;
    private static double lat = 38.969398;
    private static double lng = -77.386398;
    private static String latField = "lat";
    private static String lngField = "lng";
    private static List<CartesianTierPlotter> ctps = new LinkedList<CartesianTierPlotter>();
    private static String geoHashPrefix = "_geoHash_";

    private static Projector project = new SinusoidalProjector();

    @Test
    public void testCartesianShapeFilter() throws IOException {
        IndexSearcher searcher = new IndexSearcher(directory, true);
        double miles = 0.5;

        CartesianShapeFilterBuilder builder = new CartesianShapeFilterBuilder(CartesianTierPlotter.DEFALT_FIELD_PREFIX);
        Filter cartesianShapeFilter = builder.buildFilter(lat, lng, miles);

        Query termQuery = new TermQuery(new Term("metafile", "doc"));
        TopDocs topDocs = searcher.search(termQuery, cartesianShapeFilter, 100);

        assertEquals(9, topDocs.totalHits);
    }

    // ================================================ Helper Methods =================================================

    @BeforeClass
    public static void setUp() throws IOException {
        directory = new RAMDirectory();
        IndexWriter writer = new IndexWriter(directory, new WhitespaceAnalyzer(), true, IndexWriter.MaxFieldLength.UNLIMITED);
        setUpPlotter(2, 15);
        addData(writer);
    }

    private static void setUpPlotter(int base, int top) {
        for (; base <= top; base++) {
            ctps.add(new CartesianTierPlotter(base, project));
        }
    }

    private static void addPoint(IndexWriter writer, String name, double lat, double lng) throws IOException {
        Document doc = new Document();

        doc.add(new Field("name", name, Field.Store.YES, Field.Index.ANALYZED));

        // convert the lat / long to lucene fields
        doc.add(new Field(latField, NumericUtils.doubleToPrefixCoded(lat), Field.Store.YES, Field.Index.NOT_ANALYZED));
        doc.add(new Field(lngField, NumericUtils.doubleToPrefixCoded(lng), Field.Store.YES, Field.Index.NOT_ANALYZED));

        // add a default meta field to make searching all documents easy
        doc.add(new Field("metafile", "doc", Field.Store.YES, Field.Index.ANALYZED));

        int ctpsize = ctps.size();
        for (int i = 0; i < ctpsize; i++) {
            CartesianTierPlotter ctp = ctps.get(i);
            doc.add(new Field(
                    CartesianTierPlotter.DEFALT_FIELD_PREFIX + ctp.getTierLevelId(),
                    NumericUtils.doubleToPrefixCoded(ctp.getTierBoxId(lat, lng)),
                    Field.Store.YES,
                    Field.Index.NOT_ANALYZED_NO_NORMS));

            doc.add(new Field(geoHashPrefix, GeoHashUtils.encode(lat, lng),
                    Field.Store.YES,
                    Field.Index.NOT_ANALYZED_NO_NORMS));
        }
        writer.addDocument(doc);
    }

    private static void addData(IndexWriter writer) throws IOException {
        addPoint(writer, "McCormick &amp; Schmick's Seafood Restaurant", 38.9579000, -77.3572000);
        addPoint(writer, "Jimmy's Old Town Tavern", 38.9690000, -77.3862000);
        addPoint(writer, "Ned Devine's", 38.9510000, -77.4107000);
        addPoint(writer, "Old Brogue Irish Pub", 38.9955000, -77.2884000);
        addPoint(writer, "Alf Laylah Wa Laylah", 38.8956000, -77.4258000);
        addPoint(writer, "Sully's Restaurant &amp; Supper", 38.9003000, -77.4467000);
        addPoint(writer, "TGIFriday", 38.8725000, -77.3829000);
        addPoint(writer, "Potomac Swing Dance Club", 38.9027000, -77.2639000);
        addPoint(writer, "White Tiger Restaurant", 38.9027000, -77.2638000);
        addPoint(writer, "Jammin' Java", 38.9039000, -77.2622000);
        addPoint(writer, "Potomac Swing Dance Club", 38.9027000, -77.2639000);
        addPoint(writer, "WiseAcres Comedy Club", 38.9248000, -77.2344000);
        addPoint(writer, "Glen Echo Spanish Ballroom", 38.9691000, -77.1400000);
        addPoint(writer, "Whitlow's on Wilson", 38.8889000, -77.0926000);
        addPoint(writer, "Iota Club and Cafe", 38.8890000, -77.0923000);
        addPoint(writer, "Hilton Washington Embassy Row", 38.9103000, -77.0451000);
        addPoint(writer, "HorseFeathers, Bar & Grill", 39.01220000000001, -77.3942);

        writer.commit();
        writer.close();
    }
}
